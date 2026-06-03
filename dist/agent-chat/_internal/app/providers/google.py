import json
import httpx
from typing import AsyncIterator
from app.providers.base import BaseProvider, LLMRequest, LLMResponse, ProviderError


class GoogleProvider(BaseProvider):
    def _build_url(self, request: LLMRequest) -> str:
        return f"https://generativelanguage.googleapis.com/v1beta/models/{request.model}:generateContent"

    def _build_contents(self, request: LLMRequest) -> list[dict]:
        contents = []
        for msg in request.messages:
            role = "user" if msg["role"] in ("user", "system") else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        return contents

    def _build_payload(self, request: LLMRequest) -> dict:
        payload: dict = {
            "contents": self._build_contents(request),
            "generationConfig": {"maxOutputTokens": request.max_tokens},
        }
        if request.system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": request.system_prompt}]
            }
        return payload

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload = self._build_payload(request)
        url = f"{self._build_url(request)}?key={request.api_key}"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code == 401 or resp.status_code == 403:
            raise ProviderError("Invalid API key", status_code=401, retryable=False)
        if resp.status_code == 429:
            raise ProviderError("Rate limited", status_code=429, retryable=True)
        if resp.status_code >= 500:
            raise ProviderError(f"Server error: {resp.status_code}", status_code=resp.status_code, retryable=True)
        if resp.status_code != 200:
            raise ProviderError(f"Unexpected status: {resp.status_code}", status_code=resp.status_code, retryable=False)

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ProviderError("API returned empty candidates (content filtered)", status_code=422, retryable=False)
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise ProviderError("API returned empty parts (content filtered)", status_code=422, retryable=False)
        content = parts[0].get("text") or ""
        return LLMResponse(content=content, model=request.model)

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        payload = self._build_payload(request)
        url = f"{self._build_url(request)}:streamGenerateContent?alt=sse&key={request.api_key}"
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    if resp.status_code in (401, 403):
                        raise ProviderError("Invalid API key", status_code=401, retryable=False)
                    raise ProviderError(f"Error: {resp.status_code}", status_code=resp.status_code, retryable=True)

                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            chunk = json.loads(data_str)
                            candidates = chunk.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts:
                                    text = parts[0].get("text", "")
                                    if text:
                                        yield text
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
