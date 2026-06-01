import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.providers.openai import OpenAIProvider
from app.providers.anthropic import AnthropicProvider
from app.providers.google import GoogleProvider
from app.providers.base import LLMRequest, ProviderError


class MockStreamResponse:
    """An async context manager that mimics httpx streaming response."""
    def __init__(self, status_code=200, lines=None):
        self.status_code = status_code
        self._lines = lines or []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class MockClient:
    """Mock httpx.AsyncClient that supports both post() and stream()."""
    def __init__(self, post_response=None, stream_response=None):
        self._post_response = post_response
        self._stream_response = stream_response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, *args, **kwargs):
        return self._post_response

    def stream(self, *args, **kwargs):
        return self._stream_response


@pytest.mark.asyncio
async def test_openai_generate_success():
    provider = OpenAIProvider()
    request = LLMRequest(model="gpt-4o", api_key="test-key", system_prompt=None, messages=[])

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": "Hello!"}}]}

    with patch("httpx.AsyncClient", return_value=MockClient(post_response=mock_response)):
        result = await provider.generate(request)
        assert result.content == "Hello!"
        assert result.model == "gpt-4o"


@pytest.mark.asyncio
async def test_openai_generate_unauthorized():
    provider = OpenAIProvider()
    request = LLMRequest(model="gpt-4o", api_key="bad-key", system_prompt=None, messages=[])

    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("httpx.AsyncClient", return_value=MockClient(post_response=mock_response)):
        with pytest.raises(ProviderError) as exc:
            await provider.generate(request)
        assert exc.value.status_code == 401
        assert exc.value.retryable is False


@pytest.mark.asyncio
async def test_openai_generate_stream():
    provider = OpenAIProvider()
    request = LLMRequest(model="gpt-4o", api_key="test-key", system_prompt=None, messages=[])

    stream_resp = MockStreamResponse(status_code=200, lines=[
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        'data: [DONE]',
    ])

    with patch("httpx.AsyncClient", return_value=MockClient(stream_response=stream_resp)):
        tokens = []
        async for token in provider.generate_stream(request):
            tokens.append(token)
        assert "".join(tokens) == "Hello world"


@pytest.mark.asyncio
async def test_anthropic_generate_success():
    provider = AnthropicProvider()
    request = LLMRequest(model="claude-sonnet-4-6", api_key="test-key", system_prompt="Be helpful", messages=[
        {"role": "user", "content": "Hi"}
    ])

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"content": [{"text": "Hello!"}]}

    with patch("httpx.AsyncClient", return_value=MockClient(post_response=mock_response)):
        result = await provider.generate(request)
        assert result.content == "Hello!"


@pytest.mark.asyncio
async def test_anthropic_generate_stream():
    provider = AnthropicProvider()
    request = LLMRequest(model="claude-sonnet-4-6", api_key="test-key", system_prompt=None, messages=[
        {"role": "user", "content": "Hi"}
    ])

    stream_resp = MockStreamResponse(status_code=200, lines=[
        'data: {"type":"content_block_delta","delta":{"text":"Hello"}}',
        'data: {"type":"content_block_delta","delta":{"text":" Claude"}}',
    ])

    with patch("httpx.AsyncClient", return_value=MockClient(stream_response=stream_resp)):
        tokens = []
        async for token in provider.generate_stream(request):
            tokens.append(token)
        assert "".join(tokens) == "Hello Claude"


@pytest.mark.asyncio
async def test_google_generate_success():
    provider = GoogleProvider()
    request = LLMRequest(model="gemini-2.0-flash", api_key="test-key", system_prompt=None, messages=[
        {"role": "user", "content": "Hi"}
    ])

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Hello!"}]}}]}

    with patch("httpx.AsyncClient", return_value=MockClient(post_response=mock_response)):
        result = await provider.generate(request)
        assert result.content == "Hello!"
