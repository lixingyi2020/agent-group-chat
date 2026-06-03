from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class LLMRequest:
    model: str
    api_key: str
    system_prompt: str | None
    messages: list[dict]  # [{"role": "user", "content": "..."}, ...]
    max_tokens: int = 500


@dataclass
class LLMResponse:
    content: str
    model: str


class BaseProvider(ABC):
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        ...

    @abstractmethod
    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        ...


class ProviderError(Exception):
    def __init__(self, message: str, status_code: int = 0, retryable: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
