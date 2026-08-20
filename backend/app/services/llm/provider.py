"""LLM 调用基础接口。

文档 §3.2 services/llm/provider.py：
支持多种 LLM provider，适配 DeepSeek / OpenAI / Qwen 等接口。
通过环境变量 LLM_PROVIDER 选择，默认 deepseek。
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.core.config import get_settings


class LLMProvider(ABC):
    """LLM provider 抽象接口。"""

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


class DeepSeekProvider(LLMProvider):
    """DeepSeek API provider。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        import httpx

        if not self.api_key:
            return self._fallback_reply(messages)

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
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _fallback_reply(self, messages: list[dict[str, str]]) -> str:
        """无 API key 时返回占位回复，避免服务完全不可用。"""
        return "[LLM_UNAVAILABLE] 请配置 DEEPSEEK_API_KEY 环境变量以启用 GPS 意图提取。"


class OpenAIProvider(LLMProvider):
    """OpenAI API provider（与 DeepSeek 接口一致）。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        import httpx

        if not self.api_key:
            return self._fallback_reply(messages)

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
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _fallback_reply(self, messages: list[dict[str, str]]) -> str:
        return "[LLM_UNAVAILABLE] 请配置 OPENAI_API_KEY 环境变量以启用 GPS 意图提取。"


_PROVIDER_MAP = {
    "deepseek": DeepSeekProvider,
    "openai": OpenAIProvider,
}


def get_llm_provider() -> LLMProvider:
    """根据环境变量选择 LLM provider。"""
    settings = get_settings()
    provider_name = os.environ.get("LLM_PROVIDER", "deepseek").lower()
    provider_cls = _PROVIDER_MAP.get(provider_name, DeepSeekProvider)
    return provider_cls()


async def chat_llm(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """全局 LLM 调用入口。"""
    provider = get_llm_provider()
    return await provider.chat(messages, temperature=temperature, max_tokens=max_tokens)
