import json
import httpx
from typing import AsyncIterator
from app.providers.base import BaseProvider, LLMRequest, LLMResponse, ProviderError


class OpenAIProvider(BaseProvider):
    BASE_URL = "https://api.openai.com/v1"

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or self.BASE_URL

    def _build_payload(self, request: LLMRequest) -> dict:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.messages)
        return {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "stream": False,
        }

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload = self._build_payload(request)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {request.api_key}",
                    "Content-Type": "application/json",
                },
            )
        if resp.status_code != 200:
            body = resp.text[:500]
            if resp.status_code == 401:
                raise ProviderError(f"Invalid API key: {body}", status_code=401, retryable=False)
            if resp.status_code == 429:
                raise ProviderError(f"Rate limited: {body}", status_code=429, retryable=True)
            if resp.status_code >= 500:
                raise ProviderError(f"Server error {resp.status_code}: {body}", status_code=resp.status_code, retryable=True)
            raise ProviderError(f"HTTP {resp.status_code}: {body}", status_code=resp.status_code, retryable=False)

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return LLMResponse(content=content, model=request.model)

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        payload = self._build_payload(request)
        payload["stream"] = True
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {request.api_key}",
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status_code != 200:
                    body = ""
                    async for line in resp.aiter_lines():
                        body += line
                        if len(body) > 500:
                            break
                    if resp.status_code == 401:
                        raise ProviderError(f"Invalid API key: {body}", status_code=401, retryable=False)
                    if resp.status_code == 429:
                        raise ProviderError(f"Rate limited: {body}", status_code=429, retryable=True)
                    if resp.status_code >= 500:
                        raise ProviderError(f"Server error {resp.status_code}: {body}", status_code=resp.status_code, retryable=True)
                    raise ProviderError(f"HTTP {resp.status_code}: {body}", status_code=resp.status_code, retryable=False)

                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
