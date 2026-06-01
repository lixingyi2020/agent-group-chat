from app.providers.base import BaseProvider
from app.providers.openai import OpenAIProvider
from app.providers.anthropic import AnthropicProvider
from app.providers.google import GoogleProvider

# Provider registry: name -> (class, default_base_url or None)
_providers: dict[str, tuple[type[BaseProvider], str | None]] = {
    "openai":       (OpenAIProvider, None),
    "anthropic":    (AnthropicProvider, None),
    "google":       (GoogleProvider, None),
    "deepseek":     (OpenAIProvider, "https://api.deepseek.com"),
    "zhipu":        (OpenAIProvider, "https://open.bigmodel.cn/api/paas/v4"),
    "kimi":         (OpenAIProvider, "https://api.moonshot.cn/v1"),
    "openai_compatible": (OpenAIProvider, None),  # user provides base_url
}


def get_provider(name: str, base_url: str | None = None) -> BaseProvider:
    entry = _providers.get(name)
    if entry is None:
        raise ValueError(f"Unknown provider: {name}")
    cls, default_url = entry
    url = base_url or default_url
    if url and issubclass(cls, OpenAIProvider):
        return cls(base_url=url)
    return cls()
