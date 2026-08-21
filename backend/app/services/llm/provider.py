"""LLM 调用基础接口。

文档 §3.2 services/llm/provider.py：
支持多种 LLM provider，适配 DeepSeek / OpenAI / Qwen 等接口。
通过环境变量 LLM_PROVIDER 选择，默认 deepseek。

核心能力：
- 结构化输出（Structured Output / JSON Schema 校验）
- 自动重试 + 指数退避
- 错误类型区分（网络 / API / 限流）
- Fallback 降级策略
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional, TypeVar

import httpx
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ── 异常体系 ─────────────────────────────────────────────────────────────────

class LLMError(Exception):
    """LLM 调用基类异常。"""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class LLMNetworkError(LLMError):
    """网络错误（超时、连接失败），可重试。"""

    def __init__(self, message: str):
        super().__init__(message, retryable=True)


class LLMRateLimitError(LLMError):
    """API 限流，可重试。"""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message, retryable=True)
        self.retry_after = retry_after


class LLMValidationError(LLMError):
    """LLM 返回内容不符合 JSON Schema，不应重试。"""

    def __init__(self, message: str):
        super().__init__(message, retryable=False)


class LLMAuthError(LLMError):
    """认证失败（API Key 无效），不应重试。"""

    def __init__(self, message: str):
        super().__init__(message, retryable=False)


# ── Provider 抽象 ─────────────────────────────────────────────────────────────

_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class LLMProvider(ABC):
    """LLM provider 抽象接口。"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 名称。"""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """发送对话消息，返回模型回复文本。"""
        ...

    async def chat_structured(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        max_retries: int = 2,
    ) -> BaseModel:
        """发送对话消息，期望 LLM 返回符合指定 Pydantic Schema 的 JSON。

        实现策略（优先使用 provider 原生支持，否则用文本 + 解析兜底）：
        1. 尝试带 JSON Schema 的 structured output（原生支持时）
        2. 若不支持，以 text 模式调用 chat()，然后用 Pydantic 解析
        3. 解析失败时自动重试，最多重 max_retries 次
        4. 仍失败则抛出 LLMValidationError

        Args:
            messages: 对话历史
            schema: 期望的 Pydantic 模型类型
            temperature: 温度参数
            max_tokens: 最大 token 数
            max_retries: 解析失败时最大重试次数

        Returns:
            解析后的 Pydantic 模型实例
        """
        for attempt in range(max_retries + 1):
            text = await self.chat(messages, temperature=temperature, max_tokens=max_tokens)
            try:
                # 尝试 Pydantic 直接解析（处理嵌套 JSON 字符串情况）
                raw_data = text
                parsed = json.loads(text)
                if isinstance(parsed, str):
                    raw_data = parsed
                    parsed = json.loads(parsed)
                # 如果 text 本身是带 JSON 包装的字符串，取内层
                if isinstance(parsed, dict) and "text" in parsed:
                    raw_data = parsed["text"]
                    parsed = json.loads(parsed["text"])
                return schema.model_validate(parsed)
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                logger.warning(
                    "[%s] Structured output parse failed (attempt %d/%d): %s — raw: %s",
                    self.provider_name, attempt + 1, max_retries + 1, exc, text[:200],
                )
                if attempt < max_retries:
                    # 加入错误上下文，重新请求 LLM 修正格式
                    correction_msg = {
                        "role": "user",
                        "content": (
                            f"请严格返回 JSON 格式，不要包含额外文字。期望 schema："
                            f"```json\n{schema.model_json_schema()}\n```\n"
                            f"你上次返回的内容无法解析：{exc}\n"
                            f"请重新返回标准 JSON。"
                        ),
                    }
                    messages = [*messages, {"role": "assistant", "content": text}, correction_msg]
                    continue
                raise LLMValidationError(
                    f"[{self.provider_name}] LLM 返回内容不符合预期 schema，"
                    f"已重试 {max_retries} 次仍失败。错误：{exc}。原始内容：{text[:500]}"
                ) from exc
        # 不可能到达这里，但满足类型检查
        raise LLMValidationError("Unexpected error in chat_structured")


# ── DeepSeek Provider ─────────────────────────────────────────────────────────

class DeepSeekProvider(LLMProvider):
    """DeepSeek API provider，支持 chat 和 reasoning 模型。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = base_url or settings.deepseek_base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        # reasoning 模型用于复杂推理场景（可选）
        self.model = settings.deepseek_model or os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        self.reasoner_model = settings.deepseek_reasoner_model or os.environ.get("DEEPSEEK_REASONER_MODEL", "deepseek-reasoner")
        self.max_retries = 2
        self._supports_structured = True  # DeepSeek API 支持 response_format=json_object

    @property
    def provider_name(self) -> str:
        return "deepseek"

    async def _do_request(
        self,
        payload: dict[str, Any],
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        """执行单个 HTTP 请求，自动处理错误类型。"""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise LLMNetworkError(f"DeepSeek 请求超时（{timeout}s）：{exc}") from exc
        except httpx.ConnectError as exc:
            raise LLMNetworkError(f"DeepSeek 连接失败：{exc}") from exc

        status = resp.status_code

        if status == 401:
            raise LLMAuthError(f"DeepSeek API 认证失败（401）：请检查 DEEPSEEK_API_KEY")
        if status == 403:
            raise LLMAuthError(f"DeepSeek API 禁止访问（403）")
        if status == 429:
            retry_after = resp.headers.get("retry-after")
            raise LLMRateLimitError(
                f"DeepSeek API 限流（429），"
                f"{'请 ' + retry_after + 's 后重试' if retry_after else '请稍后重试'}",
                retry_after=int(retry_after) if retry_after else None,
            )
        if status >= 500:
            raise LLMNetworkError(f"DeepSeek 服务端错误（{status}）：{resp.text[:200]}")

        if not resp.is_success:
            raise LLMError(f"DeepSeek 请求失败（{status}）：{resp.text[:200]}")

        return resp.json()

    async def _request_with_retry(
        self,
        payload: dict[str, Any],
        max_retries: int = 2,
    ) -> str:
        """带指数退避的重试逻辑。"""
        last_exc: LLMError | None = None
        for attempt in range(max_retries + 1):
            try:
                data = await self._do_request(payload)
                return data["choices"][0]["message"]["content"]
            except LLMError as exc:
                last_exc = exc
                if not exc.retryable or attempt >= max_retries:
                    raise
                wait = 2 ** attempt  # 指数退避：1s, 2s
                if isinstance(exc, LLMRateLimitError) and exc.retry_after:
                    wait = max(wait, exc.retry_after)
                logger.warning(
                    "[DeepSeek] 请求失败（%s），%.1fs 后重试（%d/%d）",
                    exc, wait, attempt + 1, max_retries,
                )
                await asyncio.sleep(wait)
        raise last_exc or LLMError("DeepSeek 请求失败（未知原因）")

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        if not self.api_key:
            return "[LLM_UNAVAILABLE] 请配置 DEEPSEEK_API_KEY 环境变量以启用 LLM 调用。"

        return await self._request_with_retry(
            {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            max_retries=self.max_retries,
        )

    async def chat_structured(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        max_retries: int = 2,
    ) -> BaseModel:
        """DeepSeek 原生 structured output。"""
        for attempt in range(max_retries + 1):
            try:
                data = await self._do_request({
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {
                        "type": "json_object",
                        "json_schema": schema.model_json_schema(),
                    },
                })
                text = data["choices"][0]["message"]["content"]
                parsed = json.loads(text)
                return schema.model_validate(parsed)
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                logger.warning(
                    "[DeepSeek] Structured output parse failed (attempt %d/%d): %s",
                    attempt + 1, max_retries + 1, exc,
                )
                if attempt < max_retries:
                    correction = {
                        "role": "user",
                        "content": (
                            f"请严格返回标准 JSON，格式如下："
                            f"```json\n{schema.model_json_schema()}\n```"
                            f"\n你上次返回的内容无法解析（{exc}），请重新返回 JSON。"
                        ),
                    }
                    messages = [*messages, {"role": "assistant", "content": text or "[]"}, correction]
                    continue
                raise LLMValidationError(
                    f"[DeepSeek] 结构化输出失败，已重试 {max_retries} 次。错误：{exc}"
                ) from exc
        raise LLMValidationError("Unexpected error in DeepSeek chat_structured")


# ── OpenAI Provider ───────────────────────────────────────────────────────────

class OpenAIProvider(LLMProvider):
    """OpenAI API provider（与 DeepSeek 接口一致）。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or settings.openai_base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = settings.openai_model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.max_retries = 2

    @property
    def provider_name(self) -> str:
        return "openai"

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        if not self.api_key:
            return "[LLM_UNAVAILABLE] 请配置 OPENAI_API_KEY 环境变量以启用 LLM 调用。"

        last_exc: LLMError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        },
                    )
                if resp.status_code == 401:
                    raise LLMAuthError("OpenAI API 认证失败（401）")
                if resp.status_code == 429:
                    raise LLMRateLimitError("OpenAI API 限流（429）")
                if resp.status_code >= 500:
                    raise LLMNetworkError(f"OpenAI 服务端错误（{resp.status_code}）")
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except LLMError as exc:
                last_exc = exc
                if not exc.retryable or attempt >= self.max_retries:
                    raise
                wait = 2 ** attempt
                logger.warning(
                    "[OpenAI] 请求失败（%s），%.1fs 后重试（%d/%d）",
                    exc, wait, attempt + 1, self.max_retries,
                )
                await asyncio.sleep(wait)
        raise last_exc or LLMError("OpenAI 请求失败（未知原因）")


# ── Provider 注册表 ───────────────────────────────────────────────────────────

_PROVIDER_MAP: dict[str, type[LLMProvider]] = {
    "deepseek": DeepSeekProvider,
    "openai": OpenAIProvider,
}


def get_llm_provider() -> LLMProvider:
    """根据环境变量选择 LLM provider。"""
    settings = get_settings()
    provider_name = (settings.llm_provider or os.environ.get("LLM_PROVIDER", "deepseek")).lower()
    provider_cls = _PROVIDER_MAP.get(provider_name, DeepSeekProvider)
    return provider_cls()


async def chat_llm(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """全局 LLM 调用入口（纯文本模式）。"""
    provider = get_llm_provider()
    return await provider.chat(messages, temperature=temperature, max_tokens=max_tokens)


async def chat_llm_structured(
    messages: list[dict[str, str]],
    schema: type[BaseModel],
    *,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    max_retries: int = 2,
) -> BaseModel:
    """全局 LLM 调用入口（结构化输出模式）。"""
    provider = get_llm_provider()
    return await provider.chat_structured(
        messages,
        schema,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
    )
