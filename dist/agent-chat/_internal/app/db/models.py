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
    agent_id: Optional[int] = None
    content: str = ""
    created_at: str = ""


@dataclass
class LLMConfig:
    id: Optional[int] = None
    provider: str = "openai"
    model: str = ""
    api_key_id: Optional[int] = None
    max_response_chars: int = 200
    is_title_generator: bool = False
    created_at: str = ""


@dataclass
class Agent:
    id: Optional[int] = None
    name: str = ""
    llm_config_id: int = 0
    system_prompt: str = ""
    style_preset: str = "custom"  # "brief", "rigorous", "witty", "custom"
    participation_mode: str = "mention_only"
    probability: float = 0.3
    avatar_index: int = 0  # 0-7, which preset gradient to use
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
