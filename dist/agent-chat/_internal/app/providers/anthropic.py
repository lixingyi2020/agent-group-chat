import json
import httpx
from typing import AsyncIterator
from app.providers.base import BaseProvider, LLMRequest, LLMResponse, ProviderError


class AnthropicProvider(BaseProvider):
    BASE_URL = "https://api.anthropic.com/v1"

    def _build_payload(self, request: LLMRequest) -> dict:
        system_prompt = request.system_prompt
        user_messages = [m for m in request.messages if m["role"] != "system"]
        payload = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "messages": user_messages,
        }
        if system_prompt:
            payload["system"] = system_prompt
        return payload

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload = self._build_payload(request)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.BASE_URL}/messages",
                json=payload,
                headers={
                    "x-api-key": request.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
            )
        if resp.status_code == 401:
            raise ProviderError("Invalid API key", status_code=401, retryable=False)
        if resp.status_code == 429:
            raise ProviderError("Rate limited", status_code=429, retryable=True)
        if resp.status_code >= 500:
            raise ProviderError(f"Server error: {resp.status_code}", status_code=resp.status_code, retryable=True)
        if resp.status_code != 200:
            raise ProviderError(f"Unexpected status: {resp.status_code}", status_code=resp.status_code, retryable=False)

        data = resp.json()
        blocks = data.get("content", [])
        if not blocks:
            raise ProviderError("API returned empty content (content filtered)", status_code=422, retryable=False)
        content = blocks[0].get("text") or ""
        return LLMResponse(content=content, model=request.model)

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        payload = self._build_payload(request)
        payload["stream"] = True
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{self.BASE_URL}/messages",
                json=payload,
                headers={
                    "x-api-key": request.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status_code == 401:
                    raise ProviderError("Invalid API key", status_code=401, retryable=False)
                if resp.status_code == 429:
                    raise ProviderError("Rate limited", status_code=429, retryable=True)
                if resp.status_code >= 500:
                    raise ProviderError(f"Server error: {resp.status_code}", status_code=resp.status_code, retryable=True)
                if resp.status_code != 200:
                    raise ProviderError(f"Unexpected status: {resp.status_code}", status_code=resp.status_code, retryable=False)

                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            event = json.loads(data_str)
                            if event.get("type") == "content_block_delta":
                                delta = event.get("delta", {})
                                text = delta.get("text", "")
                                if text:
                                    yield text
                        except (json.JSONDecodeError, KeyError):
                            continue
