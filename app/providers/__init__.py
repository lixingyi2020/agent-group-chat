from app.providers.base import BaseProvider
from app.providers.openai import OpenAIProvider
from app.providers.anthropic import AnthropicProvider
from app.providers.google import GoogleProvider


_providers = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "openai_compatible": OpenAIProvider,  # uses custom base_url
}


def get_provider(name: str, base_url: str | None = None) -> BaseProvider:
    cls = _providers.get(name)
    if cls is None:
        raise ValueError(f"Unknown provider: {name}")
    if base_url and name in ("openai", "openai_compatible"):
        return cls(base_url=base_url)
    return cls()
