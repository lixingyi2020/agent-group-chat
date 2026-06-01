from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Conversation:
    id: Optional[int] = None
    title: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Message:
    id: Optional[int] = None
    conversation_id: int = 0
    role: str = "user"  # "user", "llm", "system"
    llm_config_id: Optional[int] = None
    content: str = ""
    created_at: str = ""


@dataclass
class LLMConfig:
    id: Optional[int] = None
    name: str = ""
    provider: str = "openai"
    model: str = ""
    api_key_id: Optional[int] = None
    participation_mode: str = "mention_only"  # "mention_only", "always", "probabilistic"
    probability: float = 0.3
    max_response_chars: int = 400
    system_prompt: Optional[str] = None
    created_at: str = ""


@dataclass
class ApiKey:
    id: Optional[int] = None
    provider: str = ""
    key_encrypted: str = ""
    created_at: str = ""


@dataclass
class Setting:
    key: str = ""
    value: str = ""
