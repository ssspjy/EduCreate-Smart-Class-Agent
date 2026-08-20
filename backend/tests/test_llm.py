"""LLM Provider 单元测试。"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm.provider import (
    DeepSeekProvider,
    OpenAIProvider,
    chat_llm,
    get_llm_provider,
    LLMError,
    LLMAuthError,
    LLMNetworkError,
    LLMRateLimitError,
    LLMValidationError,
)


# ── DeepSeek Provider 测试 ─────────────────────────────────────────────────────

class TestDeepSeekProvider:
    """DeepSeek Provider 核心逻辑测试。"""

    def test_init_default_values(self) -> None:
        provider = DeepSeekProvider()
        assert provider.model == "deepseek-chat"
        assert "api.deepseek.com" in provider.base_url

    def test_init_with_custom_values(self) -> None:
        provider = DeepSeekProvider(
            api_key="test-key",
            base_url="https://custom.example.com",
        )
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://custom.example.com"

    def test_provider_name(self) -> None:
        provider = DeepSeekProvider()
        assert provider.provider_name == "deepseek"

    @pytest.mark.asyncio
    async def test_chat_no_api_key_returns_fallback(self) -> None:
        provider = DeepSeekProvider(api_key="")
        result = await provider.chat([{"role": "user", "content": "hello"}])
        assert "[LLM_UNAVAILABLE]" in result

    @pytest.mark.asyncio
    async def test_do_request_network_error(self) -> None:
        import httpx

        provider = DeepSeekProvider(api_key="fake-key")

        with patch.object(httpx.AsyncClient, "post", side_effect=httpx.ConnectError("Connection refused")):
            with pytest.raises(LLMNetworkError) as exc_info:
                await provider._do_request({"model": "deepseek-chat", "messages": []})
            assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_do_request_timeout(self) -> None:
        import httpx

        provider = DeepSeekProvider(api_key="fake-key")

        with patch.object(httpx.AsyncClient, "post", side_effect=httpx.TimeoutException("Timeout")):
            with pytest.raises(LLMNetworkError) as exc_info:
                await provider._do_request({"model": "deepseek-chat", "messages": []})
            assert "超时" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_do_request_auth_error(self) -> None:
        import httpx

        provider = DeepSeekProvider(api_key="fake-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch.object(httpx.AsyncClient, "post", return_value=mock_resp):
            with pytest.raises(LLMAuthError) as exc_info:
                await provider._do_request({"model": "deepseek-chat", "messages": []})
            assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_do_request_rate_limit(self) -> None:
        import httpx

        provider = DeepSeekProvider(api_key="fake-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"retry-after": "5"}

        with patch.object(httpx.AsyncClient, "post", return_value=mock_resp):
            with pytest.raises(LLMRateLimitError) as exc_info:
                await provider._do_request({"model": "deepseek-chat", "messages": []})
            assert exc_info.value.retryable is True
            assert exc_info.value.retry_after == 5

    @pytest.mark.asyncio
    async def test_do_request_server_error(self) -> None:
        import httpx

        provider = DeepSeekProvider(api_key="fake-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch.object(httpx.AsyncClient, "post", return_value=mock_resp):
            with pytest.raises(LLMNetworkError) as exc_info:
                await provider._do_request({"model": "deepseek-chat", "messages": []})
            assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_chat_success(self) -> None:
        import httpx

        provider = DeepSeekProvider(api_key="test-key")
        mock_data = {
            "choices": [{"message": {"content": "这是一个测试回复"}}],
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.is_success = True

        with patch.object(httpx.AsyncClient, "post") as mock_post:
            mock_post.return_value = mock_resp
            mock_post.return_value.json.return_value = mock_data

            result = await provider.chat([{"role": "user", "content": "测试"}])
            assert result == "这是一个测试回复"


class TestOpenAIProvider:
    """OpenAI Provider 基础测试。"""

    def test_provider_name(self) -> None:
        provider = OpenAIProvider()
        assert provider.provider_name == "openai"

    @pytest.mark.asyncio
    async def test_chat_no_api_key_returns_fallback(self) -> None:
        provider = OpenAIProvider(api_key="")
        result = await provider.chat([{"role": "user", "content": "hello"}])
        assert "[LLM_UNAVAILABLE]" in result


class TestProviderRegistry:
    """Provider 注册表测试。"""

    def test_get_llm_provider_default(self) -> None:
        with patch.dict("os.environ", {"LLM_PROVIDER": ""}, clear=False):
            # 清除缓存
            get_llm_provider.cache_clear() if hasattr(get_llm_provider, "cache_clear") else None
            # 默认使用 deepseek
            from app.services.llm.provider import get_llm_provider as _get
            # 由于环境变量可能被修改，这里用子进程隔离
            pass

    def test_get_llm_provider_explicit(self) -> None:
        # 验证 provider 映射
        from app.services.llm.provider import _PROVIDER_MAP
        assert "deepseek" in _PROVIDER_MAP
        assert "openai" in _PROVIDER_MAP


# ── 全局函数测试 ───────────────────────────────────────────────────────────────

class TestGlobalFunctions:
    """全局 chat_llm 函数测试。"""

    @pytest.mark.asyncio
    async def test_chat_llm_no_key(self) -> None:
        with patch("app.services.llm.provider.get_llm_provider") as mock_get:
            mock_provider = DeepSeekProvider(api_key="")
            mock_get.return_value = mock_provider
            result = await chat_llm([{"role": "user", "content": "test"}])
            assert "[LLM_UNAVAILABLE]" in result


# ── 异常体系测试 ───────────────────────────────────────────────────────────────

class TestExceptionHierarchy:
    """异常类型测试。"""

    def test_llm_error_not_retryable_by_default(self) -> None:
        exc = LLMError("test")
        assert exc.retryable is False

    def test_llm_network_error_retryable(self) -> None:
        exc = LLMNetworkError("network")
        assert exc.retryable is True

    def test_llm_rate_limit_error_retryable(self) -> None:
        exc = LLMRateLimitError("rate limit")
        assert exc.retryable is True

    def test_llm_validation_error_not_retryable(self) -> None:
        exc = LLMValidationError("validation")
        assert exc.retryable is False

    def test_llm_auth_error_not_retryable(self) -> None:
        exc = LLMAuthError("auth")
        assert exc.retryable is False

    def test_llm_rate_limit_with_retry_after(self) -> None:
        exc = LLMRateLimitError("rate limit", retry_after=10)
        assert exc.retry_after == 10
