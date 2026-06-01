# Multi-LLM Group Chat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web-based group chat app where a user converses with multiple AI LLMs that can also talk to each other.

**Architecture:** Single FastAPI process using asyncio for concurrent LLM calls. HTMX + SSE for the frontend — server-rendered Jinja2 templates with no client-side JavaScript framework. SQLite via aiosqlite for persistence.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, httpx, aiosqlite, Jinja2, cryptography (Fernet), pytest + pytest-asyncio

---

## File Responsibility Map

| File | Responsibility |
|------|---------------|
| `app/main.py` | App creation, lifespan, route registration |
| `app/db/models.py` | Dataclass models |
| `app/db/migrations.py` | Schema creation |
| `app/db/queries.py` | All database operations |
| `app/crypto.py` | Fernet encrypt/decrypt for API keys |
| `app/i18n/__init__.py` | Translation lookup, cookie middleware |
| `app/i18n/zh.py` | Chinese strings |
| `app/i18n/en.py` | English strings |
| `app/providers/base.py` | Abstract provider adapter |
| `app/providers/openai.py` | OpenAI adapter |
| `app/providers/anthropic.py` | Anthropic adapter |
| `app/providers/google.py` | Google adapter |
| `app/orchestrator.py` | Participation logic, LLM generation tasks |
| `app/routes/pages.py` | Full page routes |
| `app/routes/fragments.py` | HTMX fragment routes |
| `app/routes/stream.py` | SSE streaming endpoint |
| `app/routes/settings.py` | API key + settings management |
| `app/templates/base.html` | Shell layout |
| `app/templates/pages/index.html` | Main app page |
| `app/templates/pages/settings.html` | Settings page |
| `app/templates/fragments/conversations.html` | Sidebar conversation list |
| `app/templates/fragments/messages.html` | Message history for chat area |
| `app/templates/fragments/llm-configs.html` | LLM config management panel |
| `static/style.css` | Minimal styling |
| `requirements.txt` | Python dependencies |

---

## Phase 1: Project Foundation

### Task 1: Create project skeleton and dependencies

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/db/__init__.py`
- Create: `app/providers/__init__.py`
- Create: `app/routes/__init__.py`
- Create: `app/i18n/__init__.py`
- Create: `tests/__init__.py`
- Create: `static/` (empty directory, placeholder)
- Bash: create all directories

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p app/db app/providers app/routes app/i18n app/templates/pages app/templates/fragments tests static
```

- [ ] **Step 2: Write requirements.txt**

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
httpx>=0.27.0
aiosqlite>=0.20.0
jinja2>=3.1.0
cryptography>=43.0.0
python-dotenv>=1.0.0

# dev
pytest>=8.0.0
pytest-asyncio>=0.24.0
```

- [ ] **Step 3: Create empty __init__.py files**

```bash
touch app/__init__.py app/db/__init__.py app/providers/__init__.py app/routes/__init__.py app/i18n/__init__.py tests/__init__.py
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: create project skeleton and dependencies"
```

---

### Task 2: Database models (dataclasses)

**Files:**
- Create: `app/db/models.py`

- [ ] **Step 1: Write models with dataclasses**

```python
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
```

- [ ] **Step 2: Verify imports work**

```bash
python -c "from app.db.models import Conversation, Message, LLMConfig, ApiKey, Setting; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/db/models.py
git commit -m "feat: add database dataclass models"
```

---

### Task 3: Database migrations (schema creation)

**Files:**
- Create: `app/db/migrations.py`

- [ ] **Step 1: Write migration code**

```python
import aiosqlite

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    key_encrypted TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS llm_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'openai',
    model TEXT NOT NULL DEFAULT '',
    api_key_id INTEGER,
    participation_mode TEXT NOT NULL DEFAULT 'mention_only',
    probability REAL NOT NULL DEFAULT 0.3,
    max_response_chars INTEGER NOT NULL DEFAULT 400,
    system_prompt TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'llm', 'system')),
    llm_config_id INTEGER,
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (llm_config_id) REFERENCES llm_configs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""


async def migrate(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.executescript(SCHEMA_SQL)
        await db.commit()
```

- [ ] **Step 2: Verify migration runs without error**

```bash
python -c "
import asyncio
from app.db.migrations import migrate
asyncio.run(migrate(':memory:'))
print('Migration OK')
"
```

Expected: `Migration OK`

- [ ] **Step 3: Commit**

```bash
git add app/db/migrations.py
git commit -m "feat: add database schema migration"
```

---

### Task 4: Database queries

**Files:**
- Create: `app/db/queries.py`

- [ ] **Step 1: Write database query functions**

```python
import aiosqlite
from typing import Optional
from app.db.models import Conversation, Message, LLMConfig, ApiKey, Setting

DB_PATH = "chat.db"


def _row_to_conversation(row: tuple) -> Conversation:
    return Conversation(id=row[0], title=row[1], created_at=row[2], updated_at=row[3])


def _row_to_message(row: tuple) -> Message:
    return Message(id=row[0], conversation_id=row[1], role=row[2],
                   llm_config_id=row[3], content=row[4], created_at=row[5])


def _row_to_llm_config(row: tuple) -> LLMConfig:
    return LLMConfig(id=row[0], name=row[1], provider=row[2], model=row[3],
                     api_key_id=row[4], participation_mode=row[5], probability=row[6],
                     max_response_chars=row[7], system_prompt=row[8], created_at=row[9])


def _row_to_api_key(row: tuple) -> ApiKey:
    return ApiKey(id=row[0], provider=row[1], key_encrypted=row[2], created_at=row[3])


# --- Conversations ---

async def create_conversation(title: str = "") -> Conversation:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "INSERT INTO conversations (title) VALUES (?)", (title,)
        )
        await db.commit()
        row = await db.execute("SELECT * FROM conversations WHERE id = ?", (cursor.lastrowid,))
        r = await row.fetchone()
        return Conversation(id=r[0], title=r[1], created_at=r[2], updated_at=r[3])


async def list_conversations() -> list[Conversation]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [_row_to_conversation(r) for r in rows]


async def get_conversation(conversation_id: int) -> Optional[Conversation]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        )
        row = await cursor.fetchone()
        return _row_to_conversation(row) if row else None


async def update_conversation_title(conversation_id: int, title: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
            (title, conversation_id),
        )
        await db.commit()


# --- Messages ---

async def create_message(conversation_id: int, role: str, content: str,
                         llm_config_id: Optional[int] = None) -> Message:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "INSERT INTO messages (conversation_id, role, content, llm_config_id) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, llm_config_id),
        )
        await db.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
            (conversation_id,),
        )
        await db.commit()
        row = await db.execute("SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,))
        r = await row.fetchone()
        return Message(id=r[0], conversation_id=r[1], role=r[2],
                       llm_config_id=r[3], content=r[4], created_at=r[5])


async def get_messages(conversation_id: int) -> list[Message]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_message(r) for r in rows]


# --- LLM Configs ---

async def create_llm_config(config: LLMConfig) -> LLMConfig:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """INSERT INTO llm_configs (name, provider, model, api_key_id,
               participation_mode, probability, max_response_chars, system_prompt)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (config.name, config.provider, config.model, config.api_key_id,
             config.participation_mode, config.probability, config.max_response_chars,
             config.system_prompt),
        )
        await db.commit()
        row = await db.execute("SELECT * FROM llm_configs WHERE id = ?", (cursor.lastrowid,))
        r = await row.fetchone()
        return _row_to_llm_config(r)


async def list_llm_configs() -> list[LLMConfig]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM llm_configs ORDER BY created_at ASC")
        rows = await cursor.fetchall()
        return [_row_to_llm_config(r) for r in rows]


async def get_llm_config(config_id: int) -> Optional[LLMConfig]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM llm_configs WHERE id = ?", (config_id,))
        row = await cursor.fetchone()
        return _row_to_llm_config(row) if row else None


async def update_llm_config(config: LLMConfig) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE llm_configs SET name=?, provider=?, model=?, api_key_id=?,
               participation_mode=?, probability=?, max_response_chars=?, system_prompt=?
               WHERE id=?""",
            (config.name, config.provider, config.model, config.api_key_id,
             config.participation_mode, config.probability, config.max_response_chars,
             config.system_prompt, config.id),
        )
        await db.commit()


async def delete_llm_config(config_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM llm_configs WHERE id = ?", (config_id,))
        await db.commit()


async def get_llm_configs_by_ids(config_ids: list[int]) -> list[LLMConfig]:
    if not config_ids:
        return []
    async with aiosqlite.connect(DB_PATH) as db:
        placeholders = ",".join("?" for _ in config_ids)
        cursor = await db.execute(
            f"SELECT * FROM llm_configs WHERE id IN ({placeholders})",
            config_ids,
        )
        rows = await cursor.fetchall()
        return [_row_to_llm_config(r) for r in rows]


# --- API Keys ---

async def create_api_key(key: ApiKey) -> ApiKey:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "INSERT INTO api_keys (provider, key_encrypted) VALUES (?, ?)",
            (key.provider, key.key_encrypted),
        )
        await db.commit()
        row = await db.execute("SELECT * FROM api_keys WHERE id = ?", (cursor.lastrowid,))
        r = await row.fetchone()
        return _row_to_api_key(r)


async def list_api_keys() -> list[ApiKey]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM api_keys ORDER BY created_at ASC")
        rows = await cursor.fetchall()
        return [_row_to_api_key(r) for r in rows]


async def get_api_key(key_id: int) -> Optional[ApiKey]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,))
        row = await cursor.fetchone()
        return _row_to_api_key(row) if row else None


async def delete_api_key(key_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
        await db.commit()


# --- Settings ---

async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (key, value, value),
        )
        await db.commit()
```

- [ ] **Step 2: Verify with a smoke test**

```bash
python -c "
import asyncio, os
from app.db.migrations import migrate
from app.db.queries import create_conversation, create_message, list_conversations, get_messages

async def smoke():
    os.environ['DB_PATH'] = ':memory:'
    import app.db.queries as q
    q.DB_PATH = ':memory:'
    await migrate(':memory:')
    conv = await create_conversation('test')
    assert conv.id == 1
    msg = await create_message(conv.id, 'user', 'hello')
    assert msg.content == 'hello'
    msgs = await get_messages(conv.id)
    assert len(msgs) == 1
    print('Smoke test OK')

asyncio.run(smoke())
"
```

Expected: `Smoke test OK`

- [ ] **Step 3: Commit**

```bash
git add app/db/queries.py
git commit -m "feat: add database query functions"
```

---

## Phase 2: Infrastructure

### Task 5: API key encryption (crypto)

**Files:**
- Create: `app/crypto.py`

- [ ] **Step 1: Write Fernet encryption helpers**

```python
import os
from cryptography.fernet import Fernet

_KEY_PATH = ".fernet_key"


def _get_or_create_key() -> bytes:
    if os.path.exists(_KEY_PATH):
        with open(_KEY_PATH, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    with open(_KEY_PATH, "wb") as f:
        f.write(key)
    return key


def encrypt(plaintext: str) -> str:
    f = Fernet(_get_or_create_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt(encrypted: str) -> str:
    f = Fernet(_get_or_create_key())
    return f.decrypt(encrypted.encode()).decode()
```

- [ ] **Step 2: Verify round-trip**

```bash
python -c "
from app.crypto import encrypt, decrypt
original = 'sk-test-key-12345'
enc = encrypt(original)
dec = decrypt(enc)
assert original == dec
print('Round-trip OK')
"
```

Expected: `Round-trip OK`

- [ ] **Step 3: Commit**

```bash
git add app/crypto.py .gitignore
git commit -m "feat: add Fernet-based API key encryption"
```

Update `.gitignore` to include `.fernet_key`:
```
.fernet_key
```

---

### Task 6: i18n system

**Files:**
- Create: `app/i18n/zh.py`
- Create: `app/i18n/en.py`
- Modify: `app/i18n/__init__.py`

- [ ] **Step 1: Write Chinese strings**

```python
STRINGS = {
    "app_title": "多 LLM 群聊",
    "conversations": "对话列表",
    "new_chat": "+ 新建对话",
    "send": "发送",
    "input_placeholder": "输入消息...（@ 提及 LLM）",
    "settings": "设置",
    "language": "语言",
    "llm_configs": "LLM 配置",
    "api_keys": "API 密钥",
    "add_llm": "添加 LLM",
    "add_key": "添加密钥",
    "save": "保存",
    "delete": "删除",
    "cancel": "取消",
    "generating": "生成中...",
    "timed_out": "请求超时",
    "retry": "重试",
    "check_api_key": "请检查 API 密钥",
    "rate_limited": "请求过于频繁，重试中...",
    "failed_after_retries": "重试失败",
    "stream_interrupted": "连接中断，正在重连...",
    "no_conversations": "暂无对话",
    "llms_active": "{count} 个 LLM 在线",
    "provider": "提供商",
    "model": "模型",
    "participation_mode": "参与模式",
    "mention_only": "仅 @提及",
    "always": "始终回应",
    "probabilistic": "概率回应",
    "probability": "概率",
    "max_response_chars": "最大回复字数",
    "system_prompt": "系统提示词",
    "name": "名称",
    "key": "密钥",
    "language_switched": "语言已切换",
}
```

- [ ] **Step 2: Write English strings**

```python
STRINGS = {
    "app_title": "Multi-LLM Chat",
    "conversations": "Conversations",
    "new_chat": "+ New Chat",
    "send": "Send",
    "input_placeholder": "Type a message... (@ to mention an LLM)",
    "settings": "Settings",
    "language": "Language",
    "llm_configs": "LLM Configs",
    "api_keys": "API Keys",
    "add_llm": "Add LLM",
    "add_key": "Add Key",
    "save": "Save",
    "delete": "Delete",
    "cancel": "Cancel",
    "generating": "generating...",
    "timed_out": "Request timed out",
    "retry": "Retry",
    "check_api_key": "Check your API key",
    "rate_limited": "Rate limited, retrying...",
    "failed_after_retries": "Failed after retries",
    "stream_interrupted": "Connection lost, reconnecting...",
    "no_conversations": "No conversations yet",
    "llms_active": "{count} LLMs active",
    "provider": "Provider",
    "model": "Model",
    "participation_mode": "Participation Mode",
    "mention_only": "@mention only",
    "always": "Always",
    "probabilistic": "Probabilistic",
    "probability": "Probability",
    "max_response_chars": "Max Response Chars",
    "system_prompt": "System Prompt",
    "name": "Name",
    "key": "Key",
    "language_switched": "Language switched",
}
```

- [ ] **Step 3: Write i18n __init__.py**

```python
from typing import Optional
from starlette.requests import Request
from app.i18n import zh, en

LOCALES = {"zh": zh.STRINGS, "en": en.STRINGS}
DEFAULT_LOCALE = "zh"
COOKIE_NAME = "lang"


def get_locale(request: Optional[Request] = None) -> str:
    if request:
        cookie_lang = request.cookies.get(COOKIE_NAME)
        if cookie_lang in LOCALES:
            return cookie_lang
    return DEFAULT_LOCALE


def t(key: str, locale: str = DEFAULT_LOCALE, **kwargs) -> str:
    strings = LOCALES.get(locale, LOCALES[DEFAULT_LOCALE])
    text = strings.get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text


def get_strings(locale: str) -> dict:
    return LOCALES.get(locale, LOCALES[DEFAULT_LOCALE])
```

- [ ] **Step 4: Verify translations work**

```bash
python -c "
from app.i18n import t
assert t('send', 'zh') == '发送'
assert t('send', 'en') == 'Send'
assert t('llms_active', 'zh', count='3') == '3 个 LLM 在线'
assert t('nonexistent', 'zh') == 'nonexistent'
print('i18n OK')
"
```

Expected: `i18n OK`

- [ ] **Step 5: Commit**

```bash
git add app/i18n/
git commit -m "feat: add i18n system (zh-CN + en-US)"
```

---

## Phase 3: LLM Provider Adapters

### Task 7: Provider base class

**Files:**
- Create: `app/providers/base.py`

- [ ] **Step 1: Write abstract base adapter**

```python
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
```

- [ ] **Step 2: Verify imports**

```bash
python -c "from app.providers.base import BaseProvider, LLMRequest, LLMResponse, ProviderError; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/providers/base.py
git commit -m "feat: add abstract provider base class"
```

---

### Task 8: OpenAI provider adapter

**Files:**
- Create: `app/providers/openai.py`

- [ ] **Step 1: Write OpenAI adapter**

```python
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
        if resp.status_code == 401:
            raise ProviderError("Invalid API key", status_code=401, retryable=False)
        if resp.status_code == 429:
            raise ProviderError("Rate limited", status_code=429, retryable=True)
        if resp.status_code >= 500:
            raise ProviderError(f"Server error: {resp.status_code}", status_code=resp.status_code, retryable=True)
        if resp.status_code != 200:
            raise ProviderError(f"Unexpected status: {resp.status_code}", status_code=resp.status_code, retryable=False)

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
```

- [ ] **Step 2: Write unit test**

Create `tests/test_providers.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.providers.openai import OpenAIProvider
from app.providers.base import LLMRequest, ProviderError


@pytest.mark.asyncio
async def test_openai_generate_success():
    provider = OpenAIProvider()
    request = LLMRequest(model="gpt-4o", api_key="test-key", system_prompt=None, messages=[])

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello!"}}]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await provider.generate(request)
        assert result.content == "Hello!"
        assert result.model == "gpt-4o"


@pytest.mark.asyncio
async def test_openai_generate_unauthorized():
    provider = OpenAIProvider()
    request = LLMRequest(model="gpt-4o", api_key="bad-key", system_prompt=None, messages=[])

    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with pytest.raises(ProviderError) as exc:
            await provider.generate(request)
        assert exc.value.status_code == 401
        assert exc.value.retryable is False


@pytest.mark.asyncio
async def test_openai_generate_stream():
    provider = OpenAIProvider()
    request = LLMRequest(model="gpt-4o", api_key="test-key", system_prompt=None, messages=[])

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.aiter_lines = AsyncMock(return_value=iter([
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        'data: [DONE]',
    ]))

    with patch("httpx.AsyncClient.stream", new_callable=AsyncMock) as mock_stream:
        mock_stream.return_value.__aenter__.return_value = mock_response
        tokens = []
        async for token in provider.generate_stream(request):
            tokens.append(token)
        assert "".join(tokens) == "Hello world"
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_providers.py -v
```

Expected: 3 tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/providers/openai.py tests/test_providers.py
git commit -m "feat: add OpenAI provider adapter with tests"
```

---

### Task 9: Anthropic provider adapter

**Files:**
- Create: `app/providers/anthropic.py`

- [ ] **Step 1: Write Anthropic adapter**

```python
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
        content = data["content"][0]["text"]
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
```

- [ ] **Step 2: Add Anthropic tests to tests/test_providers.py**

```python
from app.providers.anthropic import AnthropicProvider


@pytest.mark.asyncio
async def test_anthropic_generate_success():
    provider = AnthropicProvider()
    request = LLMRequest(model="claude-sonnet-4-6", api_key="test-key", system_prompt="Be helpful", messages=[
        {"role": "user", "content": "Hi"}
    ])

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": [{"text": "Hello!"}]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await provider.generate(request)
        assert result.content == "Hello!"


@pytest.mark.asyncio
async def test_anthropic_generate_stream():
    provider = AnthropicProvider()
    request = LLMRequest(model="claude-sonnet-4-6", api_key="test-key", system_prompt=None, messages=[
        {"role": "user", "content": "Hi"}
    ])

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.aiter_lines = AsyncMock(return_value=iter([
        'data: {"type":"content_block_delta","delta":{"text":"Hello"}}',
        'data: {"type":"content_block_delta","delta":{"text":" Claude"}}',
    ]))

    with patch("httpx.AsyncClient.stream", new_callable=AsyncMock) as mock_stream:
        mock_stream.return_value.__aenter__.return_value = mock_response
        tokens = []
        async for token in provider.generate_stream(request):
            tokens.append(token)
        assert "".join(tokens) == "Hello Claude"
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_providers.py -v
```

Expected: 5 tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/providers/anthropic.py tests/test_providers.py
git commit -m "feat: add Anthropic provider adapter with tests"
```

---

### Task 10: Google Gemini provider adapter

**Files:**
- Create: `app/providers/google.py`

- [ ] **Step 1: Write Google adapter**

```python
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
        content = data["candidates"][0]["content"]["parts"][0]["text"]
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
```

- [ ] **Step 2: Add Google tests to tests/test_providers.py**

```python
from app.providers.google import GoogleProvider


@pytest.mark.asyncio
async def test_google_generate_success():
    provider = GoogleProvider()
    request = LLMRequest(model="gemini-2.0-flash", api_key="test-key", system_prompt=None, messages=[
        {"role": "user", "content": "Hi"}
    ])

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Hello!"}]}}]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await provider.generate(request)
        assert result.content == "Hello!"
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_providers.py -v
```

Expected: 6 tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/providers/google.py tests/test_providers.py
git commit -m "feat: add Google Gemini provider adapter with tests"
```

---

### Task 11: Provider factory

**Files:**
- Modify: `app/providers/__init__.py`

- [ ] **Step 1: Write provider registry**

```python
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
```

- [ ] **Step 2: Verify**

```bash
python -c "
from app.providers import get_provider
from app.providers.openai import OpenAIProvider
from app.providers.anthropic import AnthropicProvider
p = get_provider('openai')
assert isinstance(p, OpenAIProvider)
p = get_provider('anthropic')
assert isinstance(p, AnthropicProvider)
print('Factory OK')
"
```

Expected: `Factory OK`

- [ ] **Step 3: Commit**

```bash
git add app/providers/__init__.py
git commit -m "feat: add provider factory registry"
```

---

## Phase 4: Orchestrator

### Task 12: Participation logic

**Files:**
- Create: `app/orchestrator.py`

- [ ] **Step 1: Write participation decision logic**

```python
import re
import random
from app.db.models import LLMConfig


MENTION_RE = re.compile(r"@(\S+)")


def extract_mentions(text: str) -> list[str]:
    return MENTION_RE.findall(text)


def should_respond(config: LLMConfig, message_text: str, is_self: bool = False,
                   mention_names: list[str] | None = None) -> bool:
    if mention_names is None:
        mention_names = extract_mentions(message_text)

    if config.name in mention_names:
        return True

    if is_self:
        return False

    if config.participation_mode == "always":
        return True

    if config.participation_mode == "probabilistic":
        return random.random() < config.probability

    return False
```

- [ ] **Step 2: Write unit tests**

Create `tests/test_participation.py`:

```python
from app.db.models import LLMConfig
from app.orchestrator import should_respond, extract_mentions


def test_extract_mentions():
    assert extract_mentions("Hello @claude what do you think?") == ["claude"]
    assert extract_mentions("@claude and @gpt help me") == ["claude", "gpt"]
    assert extract_mentions("No mentions here") == []
    assert extract_mentions("@mention-with-dashes") == ["mention-with-dashes"]


def test_mention_always_responds():
    config = LLMConfig(name="claude", participation_mode="mention_only")
    assert should_respond(config, "Hey @claude", mention_names=["claude"]) is True


def test_mention_overrides_all_modes():
    config = LLMConfig(name="claude", participation_mode="mention_only")
    assert should_respond(config, "Hey @claude", mention_names=["claude"]) is True


def test_always_mode_responds():
    config = LLMConfig(name="claude", participation_mode="always")
    assert should_respond(config, "Just a normal message") is True


def test_mention_only_skips_without_mention():
    config = LLMConfig(name="claude", participation_mode="mention_only")
    assert should_respond(config, "Just a normal message") is False


def test_probabilistic_0_never_responds():
    config = LLMConfig(name="claude", participation_mode="probabilistic", probability=0.0)
    responses = [should_respond(config, "msg") for _ in range(100)]
    assert all(r is False for r in responses)


def test_probabilistic_1_always_responds():
    config = LLMConfig(name="claude", participation_mode="probabilistic", probability=1.0)
    responses = [should_respond(config, "msg") for _ in range(100)]
    assert all(r is True for r in responses)


def test_self_reply_prevented():
    config = LLMConfig(name="claude", participation_mode="always")
    assert should_respond(config, "my own message", is_self=True) is False


def test_self_reply_allowed_when_mentioned():
    config = LLMConfig(name="claude", participation_mode="always")
    assert should_respond(config, "I agree with @claude", is_self=True, mention_names=["claude"]) is True
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_participation.py -v
```

Expected: 9 tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/orchestrator.py tests/test_participation.py
git commit -m "feat: add LLM participation trigger logic with tests"
```

---

### Task 13: LLM generation task runner

**Files:**
- Modify: `app/orchestrator.py` (append generation task logic and retry wrapper)

- [ ] **Step 1: Add retry wrapper to orchestrator.py**

```python
import asyncio
import logging
from typing import TypeVar, Callable, Awaitable
from app.providers.base import ProviderError

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def with_retries(fn: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
    """Retry on transient errors: 3x exponential backoff for rate limits, 1x for 5xx."""
    last_error = None
    for attempt in range(3):
        try:
            return await fn(*args, **kwargs)
        except ProviderError as e:
            last_error = e
            if not e.retryable:
                raise
            if e.status_code == 429 and attempt < 2:
                delay = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1}/3)")
                await asyncio.sleep(delay)
            elif e.status_code >= 500 and attempt == 0:
                logger.warning(f"Server error {e.status_code}, retrying once after 2s")
                await asyncio.sleep(2)
            else:
                raise
    raise last_error  # type: ignore
```

- [ ] **Step 2: Add generation task and orchestration to orchestrator.py**

Append to `app/orchestrator.py`:

```python
import asyncio
import logging
from typing import Optional
from app.db.models import LLMConfig, Message
from app.db import queries
from app.providers import get_provider
from app.providers.base import LLMRequest, ProviderError
from app.crypto import decrypt

logger = logging.getLogger(__name__)

MAX_CHAIN_DEPTH = 2
MAX_CONCURRENT = 5


async def _build_messages(conversation_id: int) -> list[dict]:
    db_messages = await queries.get_messages(conversation_id)
    return [{"role": m.role, "content": m.content} for m in db_messages]


async def _run_llm_generation(
    config: LLMConfig,
    conversation_id: int,
    event_queue: asyncio.Queue,
    depth: int = 0,
) -> Optional[Message]:
    try:
        api_key_record = await queries.get_api_key(config.api_key_id)
        if not api_key_record:
            raise ProviderError(f"No API key configured for {config.provider}", status_code=0, retryable=False)

        api_key = decrypt(api_key_record.key_encrypted)
        messages = await _build_messages(conversation_id)

        request = LLMRequest(
            model=config.model,
            api_key=api_key,
            system_prompt=config.system_prompt,
            messages=messages,
            max_tokens=config.max_response_chars,
        )

        provider = get_provider(config.provider)
        full_content = ""

        # Use streaming (no internal retry — failed streams show error + manual retry link).
        # The with_retries wrapper is used via the non-streaming generate() fallback
        # for auto-responses where real-time display is less critical.
        async for token in provider.generate_stream(request):
            full_content += token
            await event_queue.put({
                "type": "chunk",
                "llm_config_id": config.id,
                "token": token,
            })

        message = await queries.create_message(
            conversation_id, "llm", full_content, config.id
        )

        await event_queue.put({
            "type": "done",
            "llm_config_id": config.id,
            "message_id": message.id,
        })

        # Check for LLM-to-LLM mentions
        if depth < MAX_CHAIN_DEPTH:
            mentions = extract_mentions(full_content)
            if mentions:
                all_configs = await queries.list_llm_configs()
                for mentioned_config in all_configs:
                    if mentioned_config.name in mentions and mentioned_config.id != config.id:
                        await _run_llm_generation(
                            mentioned_config, conversation_id, event_queue, depth + 1
                        )

        return message

    except ProviderError as e:
        if e.retryable:
            # One retry with non-streaming generate() for transient errors
            try:
                response = await with_retries(provider.generate, request)
                full_content = response.content
                await event_queue.put({"type": "chunk", "llm_config_id": config.id, "token": full_content})
                message = await queries.create_message(conversation_id, "llm", full_content, config.id)
                await event_queue.put({"type": "done", "llm_config_id": config.id, "message_id": message.id})
                return message
            except Exception:
                pass
        await event_queue.put({
            "type": "error",
            "llm_config_id": config.id,
            "error": str(e),
            "retryable": e.retryable,
        })
        return None
    except Exception as e:
        logger.exception(f"Unexpected error for LLM {config.name}")
        await event_queue.put({
            "type": "error",
            "llm_config_id": config.id,
            "error": str(e),
            "retryable": False,
        })
        return None


async def orchestrate_llm_responses(
    conversation_id: int,
    event_queue: asyncio.Queue,
    triggering_message_text: str,
    triggering_llm_config_id: Optional[int] = None,
    depth: int = 0,
) -> None:
    configs = await queries.list_llm_configs()
    mention_names = extract_mentions(triggering_message_text)

    tasks_to_run = []
    for config in configs:
        is_self = config.id == triggering_llm_config_id
        if should_respond(config, triggering_message_text, is_self=is_self, mention_names=mention_names):
            tasks_to_run.append(config)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def _run_with_limit(config: LLMConfig):
        async with semaphore:
            await _run_llm_generation(config, conversation_id, event_queue, depth)

    await asyncio.gather(*[_run_with_limit(c) for c in tasks_to_run])
```

- [ ] **Step 2: Verify module imports**

```bash
python -c "from app.orchestrator import should_respond, extract_mentions, orchestrate_llm_responses, _run_llm_generation; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/orchestrator.py
git commit -m "feat: add LLM generation task runner and orchestration"
```

---

## Phase 5: SSE Streaming

### Task 14: SSE streaming endpoint

**Files:**
- Create: `app/routes/stream.py`

- [ ] **Step 1: Write SSE route**

```python
import asyncio
import json
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()

# In-memory store: conversation_id -> asyncio.Queue
_streams: dict[int, asyncio.Queue] = {}


def get_or_create_queue(conversation_id: int) -> asyncio.Queue:
    if conversation_id not in _streams:
        _streams[conversation_id] = asyncio.Queue()
    return _streams[conversation_id]


def remove_queue(conversation_id: int) -> None:
    _streams.pop(conversation_id, None)


async def event_generator(conversation_id: int, request: Request):
    queue = get_or_create_queue(conversation_id)
    quiet_count = 0
    while True:
        if await request.is_disconnected():
            break
        try:
            event = await asyncio.wait_for(queue.get(), timeout=5.0)
            quiet_count = 0
            yield {
                "event": event["type"],
                "data": json.dumps({k: v for k, v in event.items() if k != "type"}),
            }
        except asyncio.TimeoutError:
            quiet_count += 1
            if quiet_count >= 2:
                break


@router.get("/stream/conversations/{conversation_id}")
async def stream_conversation(conversation_id: int, request: Request):
    return EventSourceResponse(event_generator(conversation_id, request))
```

Note: Since sse_starlette adds a dependency, alternatively implement SSE manually:

- [ ] **Step 1 (alternative — no extra dependency): Write SSE route with manual SSE**

```python
import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

_streams: dict[int, asyncio.Queue] = {}


def get_or_create_queue(conversation_id: int) -> asyncio.Queue:
    if conversation_id not in _streams:
        _streams[conversation_id] = asyncio.Queue()
    return _streams[conversation_id]


def remove_queue(conversation_id: int) -> None:
    _streams.pop(conversation_id, None)


async def event_generator(conversation_id: int, request: Request):
    queue = get_or_create_queue(conversation_id)
    quiet_count = 0
    while True:
        if await request.is_disconnected():
            break
        try:
            event = await asyncio.wait_for(queue.get(), timeout=5.0)
            quiet_count = 0
            event_type = event["type"]
            payload = json.dumps({k: v for k, v in event.items() if k != "type"})
            yield f"event: {event_type}\ndata: {payload}\n\n"
        except asyncio.TimeoutError:
            quiet_count += 1
            if quiet_count >= 2:
                break


@router.get("/stream/conversations/{conversation_id}")
async def stream_conversation(conversation_id: int, request: Request):
    return StreamingResponse(
        event_generator(conversation_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 2: Write SSE integration test**

```python
@pytest.mark.asyncio
async def test_sse_event_generator():
    from app.routes.stream import get_or_create_queue, remove_queue, event_generator

    queue = get_or_create_queue(1)
    await queue.put({"type": "chunk", "llm_config_id": 1, "token": "Hello"})
    await queue.put({"type": "done", "llm_config_id": 1, "message_id": 42})

    # Clean up
    remove_queue(1)
```

Add the test to `tests/test_routes.py`.

- [ ] **Step 3: Verify SSE route loads**

```bash
python -c "from app.routes.stream import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/routes/stream.py
git commit -m "feat: add SSE streaming endpoint"
```

---

## Phase 6: HTML Templates

### Task 15: Base HTML shell and CSS

**Files:**
- Create: `app/templates/base.html`
- Create: `static/style.css`

- [ ] **Step 1: Write base HTML template**

```html
<!DOCTYPE html>
<html lang="{{ locale }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ strings.app_title }}</title>
    <link rel="stylesheet" href="/static/style.css">
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <script src="https://unpkg.com/htmx.org@2.0.4/dist/ext/sse.js"></script>
    <script>
        // SSE event handler: routes chunk/done/error events to matching placeholders.
        // HTMX's hx-sse handles the connection; this script handles per-event DOM updates.
        document.body.addEventListener("htmx:sseBeforeMessage", function(evt) {
            // evt.detail contains the parsed SSE event
        });
        // After each HTMX request that triggers SSE, connect to the stream.
        document.body.addEventListener("htmx:afterOnLoad", function(evt) {
            const triggerHeader = evt.detail.xhr.getResponseHeader("HX-Trigger");
            if (triggerHeader && triggerHeader.includes("sseConnect")) {
                const path = window.location.pathname;
                const match = path.match(/\/conversations\/(\d+)/);
                if (match) {
                    const convId = match[1];
                    const es = new EventSource("/stream/conversations/" + convId);
                    es.addEventListener("chunk", function(e) {
                        const data = JSON.parse(e.data);
                        const el = document.getElementById("placeholder-" + data.llm_config_id);
                        if (el) {
                            const bubble = el.querySelector(".message-bubble");
                            if (bubble) {
                                bubble.textContent += data.token;
                                el.classList.remove("generating");
                            }
                        }
                    });
                    es.addEventListener("done", function(e) {
                        const data = JSON.parse(e.data);
                        const el = document.getElementById("placeholder-" + data.llm_config_id);
                        if (el) el.classList.remove("generating");
                        es.close();
                    });
                    es.addEventListener("error", function(e) {
                        try {
                            const data = JSON.parse(e.data);
                            const el = document.getElementById("placeholder-" + data.llm_config_id);
                            if (el) {
                                const bubble = el.querySelector(".message-bubble");
                                if (bubble) bubble.textContent = "[Error] " + (data.error || "");
                                el.classList.remove("generating");
                            }
                        } catch (_) {}
                        es.close();
                    });
                }
            }
        });
    </script>
</head>
<body hx-ext="sse">
    <div class="app-container">
        <aside class="sidebar" id="sidebar">
            {% block sidebar %}{% endblock %}
        </aside>
        <main class="main-content" id="main-content">
            {% block content %}{% endblock %}
        </main>
    </div>
</body>
</html>
```

- [ ] **Step 2: Write CSS**

```css
*, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

:root {
    --bg-primary: #020617;
    --bg-secondary: #0f172a;
    --bg-tertiary: #1e293b;
    --border-color: #1e293b;
    --text-primary: #e2e8f0;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --user-msg-bg: #1d4ed8;
    --accent-blue: #38bdf8;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    height: 100vh;
    overflow: hidden;
}

.app-container {
    display: flex;
    height: 100vh;
}

.sidebar {
    width: 260px;
    min-width: 260px;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
}

.sidebar-header {
    padding: 16px;
    border-bottom: 1px solid var(--border-color);
    font-weight: 600;
    font-size: 14px;
}

.sidebar-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
}

.conversation-item {
    padding: 10px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 2px;
    display: block;
    text-decoration: none;
}

.conversation-item:hover {
    background: var(--bg-tertiary);
}

.conversation-item.active {
    background: var(--bg-tertiary);
    color: var(--accent-blue);
}

.sidebar-footer {
    padding: 8px;
    border-top: 1px solid var(--border-color);
}

.main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.chat-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 14px;
}

.chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.message {
    display: flex;
    gap: 8px;
    max-width: 75%;
}

.message.user {
    align-self: flex-end;
    flex-direction: row-reverse;
}

.message-avatar {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 600;
    color: white;
    flex-shrink: 0;
}

.message-body {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.message-sender {
    font-size: 11px;
    color: var(--text-muted);
    margin-bottom: 2px;
}

.message-bubble {
    padding: 8px 14px;
    border-radius: 12px;
    font-size: 13px;
    line-height: 1.5;
    word-wrap: break-word;
}

.message.user .message-bubble {
    background: var(--user-msg-bg);
    border-bottom-right-radius: 2px;
}

.message.llm .message-bubble {
    background: var(--bg-tertiary);
    border-bottom-left-radius: 2px;
}

.chat-input-bar {
    padding: 12px 16px;
    border-top: 1px solid var(--border-color);
    display: flex;
    gap: 8px;
}

.chat-input-bar input {
    flex: 1;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 10px 14px;
    color: var(--text-primary);
    font-size: 13px;
    outline: none;
}

.chat-input-bar input:focus {
    border-color: var(--accent-blue);
}

.chat-input-bar button {
    background: var(--accent-blue);
    color: var(--bg-primary);
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
}

.btn-secondary {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 12px;
    cursor: pointer;
    width: 100%;
    text-align: center;
}

.btn-secondary:hover {
    background: var(--border-color);
}

.lang-switcher {
    display: flex;
    gap: 6px;
    align-items: center;
    padding: 8px;
    font-size: 11px;
    color: var(--text-muted);
}

.lang-switcher select {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 4px 6px;
    font-size: 11px;
    flex: 1;
}

.generating {
    opacity: 0.6;
    font-style: italic;
}

.empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    font-size: 14px;
}

.settings-link {
    color: var(--text-muted);
    text-decoration: none;
    font-size: 12px;
    padding: 4px 8px;
}

.settings-link:hover {
    color: var(--text-primary);
}

/* LLM avatar colors */
.avatar-0 { background: #7c3aed; }
.avatar-1 { background: #059669; }
.avatar-2 { background: #d97706; }
.avatar-3 { background: #dc2626; }
.avatar-4 { background: #2563eb; }
.avatar-5 { background: #7c3aed; }
.avatar-6 { background: #0891b2; }
.avatar-7 { background: #ca8a04; }
```

- [ ] **Step 3: Commit**

```bash
git add app/templates/base.html static/style.css
git commit -m "feat: add base HTML template and CSS styles"
```

---

### Task 16: Fragment templates

**Files:**
- Create: `app/templates/fragments/conversations.html`
- Create: `app/templates/fragments/messages.html`
- Create: `app/templates/fragments/llm-configs.html`

- [ ] **Step 1: Write conversations sidebar fragment**

```html
<div class="sidebar-header">{{ strings.conversations }}</div>
<div class="sidebar-list" id="conversation-list">
    {% if conversations %}
        {% for conv in conversations %}
        <a href="/conversations/{{ conv.id }}"
           class="conversation-item {% if active_id == conv.id %}active{% endif %}"
           hx-get="/fragments/conversations/{{ conv.id }}/messages"
           hx-target="#chat-messages"
           hx-push-url="/conversations/{{ conv.id }}">
            {{ conv.title or "Untitled" }}
        </a>
        {% endfor %}
    {% else %}
        <div class="empty-state">{{ strings.no_conversations }}</div>
    {% endif %}
</div>
<div class="sidebar-footer">
    <button class="btn-secondary"
            hx-post="/fragments/conversations"
            hx-target="#sidebar"
            hx-swap="outerHTML">
        {{ strings.new_chat }}
    </button>
    <div class="lang-switcher">
        <span>{{ strings.language }}</span>
        <select name="lang" hx-post="/fragments/settings/language" hx-swap="none">
            <option value="zh" {% if locale == 'zh' %}selected{% endif %}>中文</option>
            <option value="en" {% if locale == 'en' %}selected{% endif %}>English</option>
        </select>
    </div>
</div>
```

- [ ] **Step 2: Write messages fragment**

```html
<div class="chat-header">
    <span>{{ conversation.title or strings.app_title }}</span>
    <div style="display: flex; gap: 12px; align-items: center;">
        <span style="color: var(--text-muted); font-size: 11px;">
            {{ strings.llms_active.replace('{count}', llm_count|string) }}
        </span>
        <a href="/settings" class="settings-link">⚙ {{ strings.settings }}</a>
    </div>
</div>
<div class="chat-messages" id="chat-messages"
     hx-sse="connect:/stream/conversations/{{ conversation.id }} swap:placeholder">
    {% for msg in messages %}
        {% if msg.role == 'user' %}
        <div class="message user">
            <div class="message-body">
                <div class="message-bubble">{{ msg.content }}</div>
            </div>
        </div>
        {% elif msg.role == 'llm' %}
        <div class="message llm">
            {% set avatar_class = 'avatar-' + (msg.llm_config_id % 8)|string %}
            <div class="message-avatar {{ avatar_class }}">
                {{ msg.llm_name[0] if msg.llm_name else '?' }}
            </div>
            <div class="message-body">
                <div class="message-sender">{{ msg.llm_name or 'LLM' }}</div>
                <div class="message-bubble">{{ msg.content }}</div>
            </div>
        </div>
        {% endif %}
    {% endfor %}
</div>
<div class="chat-input-bar">
    <input type="text" name="content" id="message-input"
           placeholder="{{ strings.input_placeholder }}"
           hx-post="/fragments/conversations/{{ conversation.id }}/messages"
           hx-target="#chat-messages"
           hx-swap="beforeend"
           hx-include="#message-input"
           hx-on::after-request="this.value = ''"
           autocomplete="off">
    <button onclick="document.getElementById('message-input').dispatchEvent(new Event('htmx:trigger'))">
        {{ strings.send }}
    </button>
</div>
```

- [ ] **Step 3: Write LLM configs fragment**

```html
<div style="padding: 24px; max-width: 600px;">
    <h2 style="margin-bottom: 16px;">{{ strings.llm_configs }}</h2>

    {% for config in configs %}
    <div style="background: var(--bg-tertiary); border-radius: 8px; padding: 14px; margin-bottom: 10px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <strong>{{ config.name }}</strong>
            <span style="font-size: 11px; color: var(--text-muted);">{{ config.provider }} / {{ config.model }}</span>
        </div>
        <div style="font-size: 12px; color: var(--text-secondary);">
            {{ strings.participation_mode }}: {{ config.participation_mode }}
        </div>
        <button class="btn-secondary" style="margin-top: 8px;"
                hx-delete="/fragments/llm-configs/{{ config.id }}"
                hx-target="closest div"
                hx-swap="outerHTML">
            {{ strings.delete }}
        </button>
    </div>
    {% endfor %}

    <details style="margin-top: 16px;">
        <summary style="cursor: pointer; color: var(--accent-blue); font-size: 14px;">
            {{ strings.add_llm }}
        </summary>
        <form style="margin-top: 12px; display: flex; flex-direction: column; gap: 10px;"
              hx-post="/fragments/llm-configs"
              hx-target="previous div"
              hx-swap="beforebegin">
            <input name="name" placeholder="{{ strings.name }}" required
                   style="background: var(--bg-tertiary); border: 1px solid var(--border-color);
                          border-radius: 6px; padding: 8px; color: var(--text-primary); font-size: 13px;">
            <select name="provider" required
                    style="background: var(--bg-tertiary); border: 1px solid var(--border-color);
                           border-radius: 6px; padding: 8px; color: var(--text-primary); font-size: 13px;">
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
            </select>
            <input name="model" placeholder="{{ strings.model }} (e.g. gpt-4o)" required
                   style="background: var(--bg-tertiary); border: 1px solid var(--border-color);
                          border-radius: 6px; padding: 8px; color: var(--text-primary); font-size: 13px;">
            <select name="participation_mode" required
                    style="background: var(--bg-tertiary); border: 1px solid var(--border-color);
                           border-radius: 6px; padding: 8px; color: var(--text-primary); font-size: 13px;">
                <option value="mention_only">{{ strings.mention_only }}</option>
                <option value="always">{{ strings.always }}</option>
                <option value="probabilistic">{{ strings.probabilistic }}</option>
            </select>
            <input name="api_key_id" placeholder="API Key ID" type="number" required
                   style="background: var(--bg-tertiary); border: 1px solid var(--border-color);
                          border-radius: 6px; padding: 8px; color: var(--text-primary); font-size: 13px;">
            <button class="btn-secondary" type="submit">{{ strings.save }}</button>
        </form>
    </details>
</div>
```

- [ ] **Step 4: Verify templates render**

```bash
python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('app/templates'))
for name in ['fragments/conversations.html', 'fragments/messages.html', 'fragments/llm-configs.html']:
    tmpl = env.get_template(name)
    print(f'{name}: OK')
print('All templates OK')
"
```

Expected: All templates OK

- [ ] **Step 5: Commit**

```bash
git add app/templates/fragments/
git commit -m "feat: add HTMX fragment templates"
```

---

### Task 17: Page templates

**Files:**
- Create: `app/templates/pages/index.html`
- Create: `app/templates/pages/settings.html`

- [ ] **Step 1: Write index page**

```html
{% extends "base.html" %}
{% block sidebar %}
    {% include "fragments/conversations.html" %}
{% endblock %}
{% block content %}
<div id="chat-area" style="display: flex; flex-direction: column; height: 100%;">
    {% if conversation %}
        {% include "fragments/messages.html" %}
    {% else %}
        <div class="empty-state">{{ strings.no_conversations }}</div>
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 2: Write settings page**

```html
{% extends "base.html" %}
{% block sidebar %}
    {% include "fragments/conversations.html" %}
{% endblock %}
{% block content %}
<div style="padding: 24px; max-width: 700px; overflow-y: auto; height: 100%;">
    <h2 style="margin-bottom: 20px;">{{ strings.settings }}</h2>

    <h3 style="margin-bottom: 12px;">{{ strings.api_keys }}</h3>
    {% for key in api_keys %}
    <div style="background: var(--bg-tertiary); border-radius: 8px; padding: 14px; margin-bottom: 8px;
                display: flex; justify-content: space-between; align-items: center;">
        <span>{{ key.provider }} — ••••••••</span>
        <button class="btn-secondary" style="width: auto;"
                hx-delete="/settings/keys/{{ key.id }}"
                hx-target="closest div" hx-swap="outerHTML">
            {{ strings.delete }}
        </button>
    </div>
    {% endfor %}

    <form style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 32px;"
          hx-post="/settings/keys" hx-target="this" hx-swap="outerHTML">
        <select name="provider" required
                style="background: var(--bg-tertiary); border: 1px solid var(--border-color);
                       border-radius: 6px; padding: 8px; color: var(--text-primary); font-size: 13px;">
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="google">Google</option>
        </select>
        <input name="key" type="password" placeholder="{{ strings.key }}" required
               style="background: var(--bg-tertiary); border: 1px solid var(--border-color);
                      border-radius: 6px; padding: 8px; color: var(--text-primary); font-size: 13px;">
        <button class="btn-secondary" type="submit">{{ strings.add_key }}</button>
    </form>

    <h3 style="margin-bottom: 12px;">{{ strings.llm_configs }}</h3>
    <div id="llm-configs-container" hx-get="/fragments/llm-configs" hx-trigger="load">
    </div>

    <div style="margin-top: 32px;">
        <h3 style="margin-bottom: 12px;">{{ strings.language }}</h3>
        <select name="lang" hx-post="/fragments/settings/language" hx-swap="none"
                style="background: var(--bg-tertiary); border: 1px solid var(--border-color);
                       border-radius: 6px; padding: 8px; color: var(--text-primary); font-size: 13px;">
            <option value="zh" {% if locale == 'zh' %}selected{% endif %}>中文</option>
            <option value="en" {% if locale == 'en' %}selected{% endif %}>English</option>
        </select>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add app/templates/pages/
git commit -m "feat: add page templates (index + settings)"
```

---

## Phase 7: Routes

### Task 18: Page routes

**Files:**
- Create: `app/routes/pages.py`

- [ ] **Step 1: Write page routes**

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.db import queries
from app.i18n import t, get_locale, get_strings
from app.templates import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    conversations = await queries.list_conversations()
    return templates.TemplateResponse(
        "pages/index.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversations": conversations, "conversation": None,
         "llm_count": 0},
    )


@router.get("/conversations/{conversation_id}", response_class=HTMLResponse)
async def conversation_page(conversation_id: int, request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    conversations = await queries.list_conversations()
    conversation = await queries.get_conversation(conversation_id)
    if not conversation:
        return templates.TemplateResponse(
            "pages/index.html",
            {"request": request, "locale": locale, "strings": strings,
             "conversations": conversations, "conversation": None,
             "llm_count": 0},
            status_code=404,
        )
    messages = await queries.get_messages(conversation_id)
    configs = await queries.list_llm_configs()

    # Attach llm_name to each message
    config_map = {c.id: c.name for c in configs}
    enriched = []
    for msg in messages:
        enriched.append({
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "role": msg.role,
            "llm_config_id": msg.llm_config_id,
            "content": msg.content,
            "created_at": msg.created_at,
            "llm_name": config_map.get(msg.llm_config_id, "") if msg.llm_config_id else "",
        })

    return templates.TemplateResponse(
        "pages/index.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversations": conversations, "conversation": conversation,
         "messages": enriched, "llm_count": len(configs),
         "active_id": conversation_id},
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    conversations = await queries.list_conversations()
    api_keys = await queries.list_api_keys()
    configs = await queries.list_llm_configs()
    return templates.TemplateResponse(
        "pages/settings.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversations": conversations, "api_keys": api_keys,
         "configs": configs},
    )
```

- [ ] **Step 2: Create templates package**

Create `app/templates/__init__.py`:

```python
from jinja2 import Environment, FileSystemLoader, select_autoescape
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
```

And update `.gitignore` to not ignore the templates `__init__.py` — no change needed since `.gitignore` doesn't have a pattern that would catch it.

- [ ] **Step 3: Verify routes load**

```bash
python -c "from app.routes.pages import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/routes/pages.py app/templates/__init__.py
git commit -m "feat: add page routes (index, conversation, settings)"
```

---

### Task 19: Fragment routes

**Files:**
- Create: `app/routes/fragments.py`

- [ ] **Step 1: Write fragment routes**

```python
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, Response
from app.db import queries
from app.db.models import LLMConfig
from app.i18n import t, get_locale, get_strings
from app.templates import templates
from app.orchestrator import orchestrate_llm_responses
from app.routes.stream import get_or_create_queue

router = APIRouter()


@router.get("/fragments/conversations", response_class=HTMLResponse)
async def fragment_conversations(request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    conversations = await queries.list_conversations()
    return templates.TemplateResponse(
        "fragments/conversations.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversations": conversations},
    )


@router.post("/fragments/conversations", response_class=HTMLResponse)
async def fragment_create_conversation(request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    conv = await queries.create_conversation()
    conversations = await queries.list_conversations()
    response = templates.TemplateResponse(
        "fragments/conversations.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversations": conversations, "active_id": conv.id},
    )
    response.headers["HX-Redirect"] = f"/conversations/{conv.id}"
    return response


@router.get("/fragments/conversations/{conversation_id}/messages", response_class=HTMLResponse)
async def fragment_messages(conversation_id: int, request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    conversation = await queries.get_conversation(conversation_id)
    messages = await queries.get_messages(conversation_id)
    configs = await queries.list_llm_configs()

    config_map = {c.id: c.name for c in configs}
    enriched = []
    for msg in messages:
        enriched.append({
            **msg.__dict__,
            "llm_name": config_map.get(msg.llm_config_id, "") if msg.llm_config_id else "",
        })

    return templates.TemplateResponse(
        "fragments/messages.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversation": conversation, "messages": enriched,
         "llm_count": len(configs)},
    )


@router.post("/fragments/conversations/{conversation_id}/messages", response_class=HTMLResponse)
async def fragment_post_message(conversation_id: int, content: str = Form(...), request: Request = None):
    locale = get_locale(request)
    strings = get_strings(locale)
    conversation = await queries.get_conversation(conversation_id)
    configs = await queries.list_llm_configs()

    # Save user message
    user_msg = await queries.create_message(conversation_id, "user", content)

    # Build HTML response with user message + placeholders for responding LLMs
    config_map = {c.id: c for c in configs}
    from app.orchestrator import should_respond

    responding = []
    for config in configs:
        if should_respond(config, content):
            responding.append(config)

    # Render the user message
    html_parts = [f'''<div class="message user" id="msg-{user_msg.id}">
        <div class="message-body">
            <div class="message-bubble">{user_msg.content}</div>
        </div>
    </div>''']

    # Render placeholders for each responding LLM
    avatar_colors = ["avatar-0", "avatar-1", "avatar-2", "avatar-3", "avatar-4", "avatar-5", "avatar-6", "avatar-7"]
    for i, config in enumerate(responding):
        avatar_class = avatar_colors[config.id % 8]
        html_parts.append(f'''<div class="message llm generating" id="placeholder-{config.id}">
            <div class="message-avatar {avatar_class}">{config.name[0]}</div>
            <div class="message-body">
                <div class="message-sender">{config.name}</div>
                <div class="message-bubble">{strings["generating"]}</div>
            </div>
        </div>''')

    # Trigger SSE connection via HX-Trigger header
    response = Response(content="\n".join(html_parts), media_type="text/html")
    response.headers["HX-Trigger"] = "sseConnect"

    # Kick off async orchestration (background task)
    import asyncio
    queue = get_or_create_queue(conversation_id)
    asyncio.create_task(orchestrate_llm_responses(conversation_id, queue, content))

    return response


@router.get("/fragments/llm-configs", response_class=HTMLResponse)
async def fragment_llm_configs(request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    configs = await queries.list_llm_configs()
    return templates.TemplateResponse(
        "fragments/llm-configs.html",
        {"request": request, "locale": locale, "strings": strings, "configs": configs},
    )


@router.post("/fragments/llm-configs", response_class=HTMLResponse)
async def fragment_create_llm_config(
    request: Request,
    name: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    participation_mode: str = Form("mention_only"),
    api_key_id: int = Form(...),
):
    config = LLMConfig(
        name=name, provider=provider, model=model,
        participation_mode=participation_mode, api_key_id=api_key_id,
    )
    await queries.create_llm_config(config)
    locale = get_locale(request)
    strings = get_strings(locale)
    configs = await queries.list_llm_configs()
    return templates.TemplateResponse(
        "fragments/llm-configs.html",
        {"request": request, "locale": locale, "strings": strings, "configs": configs},
    )


@router.delete("/fragments/llm-configs/{config_id}", response_class=HTMLResponse)
async def fragment_delete_llm_config(config_id: int):
    await queries.delete_llm_config(config_id)
    return Response(status_code=200)


@router.post("/fragments/settings/language")
async def fragment_set_language(request: Request, lang: str = Form(...)):
    response = Response(status_code=200)
    response.set_cookie("lang", lang)
    response.headers["HX-Refresh"] = "true"
    return response
```

- [ ] **Step 2: Verify routes load**

```bash
python -c "from app.routes.fragments import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/routes/fragments.py
git commit -m "feat: add HTMX fragment routes"
```

---

### Task 20: Settings routes

**Files:**
- Create: `app/routes/settings.py`

- [ ] **Step 1: Write settings routes**

```python
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response
from app.db import queries
from app.db.models import ApiKey
from app.crypto import encrypt
from app.i18n import get_locale, get_strings
from app.templates import templates

router = APIRouter()


@router.post("/settings/keys", response_class=HTMLResponse)
async def create_key(request: Request, provider: str = Form(...), key: str = Form(...)):
    encrypted = encrypt(key)
    await queries.create_api_key(ApiKey(provider=provider, key_encrypted=encrypted))

    locale = get_locale(request)
    strings = get_strings(locale)
    conversations = await queries.list_conversations()
    api_keys = await queries.list_api_keys()
    configs = await queries.list_llm_configs()
    return templates.TemplateResponse(
        "pages/settings.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversations": conversations, "api_keys": api_keys, "configs": configs},
    )


@router.delete("/settings/keys/{key_id}")
async def delete_key(key_id: int):
    await queries.delete_api_key(key_id)
    return Response(status_code=200)
```

- [ ] **Step 2: Commit**

```bash
git add app/routes/settings.py
git commit -m "feat: add settings routes (API key CRUD)"
```

---

## Phase 8: App Assembly

### Task 21: Main app entry point

**Files:**
- Create: `app/main.py`

- [ ] **Step 1: Write main.py**

```python
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.db.migrations import migrate
from app.db.queries import DB_PATH
from app.routes import pages, fragments, stream, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await migrate(DB_PATH)
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(pages.router)
app.include_router(fragments.router)
app.include_router(stream.router)
app.include_router(settings.router)
```

- [ ] **Step 2: Create run script**

Create `run.py` at project root:

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
```

- [ ] **Step 3: Verify app starts**

```bash
python -c "from app.main import app; print('App created OK')"
```

Expected: `App created OK`

- [ ] **Step 4: Commit**

```bash
git add app/main.py run.py
git commit -m "feat: wire up FastAPI app with all routes"
```

---

## Phase 9: Integration Tests

### Task 22: Route integration tests

**Files:**
- Create: `tests/test_routes.py`

- [ ] **Step 1: Write integration tests**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.migrations import migrate
from app.db import queries


TEST_DB = ":memory:"


@pytest.fixture(autouse=True)
async def setup_db():
    queries.DB_PATH = TEST_DB
    await migrate(TEST_DB)
    yield


@pytest.mark.asyncio
async def test_index_returns_html():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_create_conversation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/fragments/conversations")
        assert resp.status_code == 200
        assert "HX-Redirect" in resp.headers


@pytest.mark.asyncio
async def test_conversation_page():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/fragments/conversations")
        resp = await client.get("/conversations/1")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_post_message():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/fragments/conversations")
        resp = await client.post(
            "/fragments/conversations/1/messages",
            data={"content": "Hello world"},
        )
        assert resp.status_code == 200
        assert "Hello world" in resp.text


@pytest.mark.asyncio
async def test_settings_page():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/settings")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_add_api_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/settings/keys",
            data={"provider": "openai", "key": "sk-test123"},
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_add_llm_config():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First add a key
        await client.post("/settings/keys", data={"provider": "openai", "key": "sk-test123"})
        # Then add config
        resp = await client.post(
            "/fragments/llm-configs",
            data={
                "name": "TestBot",
                "provider": "openai",
                "model": "gpt-4o",
                "participation_mode": "mention_only",
                "api_key_id": "1",
            },
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_language_switch():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/fragments/settings/language", data={"lang": "en"})
        assert resp.status_code == 200
        assert "lang=en" in resp.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_i18n_defaults_to_chinese():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert "群聊" in resp.text or "发送" in resp.text
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_routes.py -v
```

Expected: 9 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_routes.py
git commit -m "test: add route integration tests"
```

---

### Task 23: Orchestrator integration test

**Files:**
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: Write orchestrator integration tests**

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.db.models import LLMConfig, ApiKey
from app.db import queries
from app.db.migrations import migrate
from app.orchestrator import orchestrate_llm_responses
from app.routes.stream import get_or_create_queue, remove_queue


TEST_DB = ":memory:"


@pytest.fixture(autouse=True)
async def setup():
    queries.DB_PATH = TEST_DB
    await migrate(TEST_DB)
    yield


@pytest.mark.asyncio
async def test_orchestrate_with_mention_only_config():
    # Create conversation + message
    conv = await queries.create_conversation("test")
    await queries.create_message(conv.id, "user", "Hello @claude")

    # Create API key + LLM config
    key = await queries.create_api_key(ApiKey(provider="openai", key_encrypted="encrypted"))
    config = LLMConfig(name="claude", provider="openai", model="gpt-4o",
                       participation_mode="mention_only", api_key_id=key.id)
    await queries.create_llm_config(config)

    queue = get_or_create_queue(conv.id)

    with patch("app.orchestrator._run_llm_generation") as mock_run:
        mock_run.return_value = None
        await orchestrate_llm_responses(conv.id, queue, "Hello @claude")

    remove_queue(conv.id)


@pytest.mark.asyncio
async def test_mention_only_skips_without_mention():
    conv = await queries.create_conversation("test")
    await queries.create_message(conv.id, "user", "Just a normal message")

    key = await queries.create_api_key(ApiKey(provider="openai", key_encrypted="encrypted"))
    config = LLMConfig(name="claude", provider="openai", model="gpt-4o",
                       participation_mode="mention_only", api_key_id=key.id)
    await queries.create_llm_config(config)

    queue = get_or_create_queue(conv.id)

    with patch("app.orchestrator._run_llm_generation") as mock_run:
        await orchestrate_llm_responses(conv.id, queue, "Just a normal message")
        # mention_only should NOT trigger without @mention
        mock_run.assert_not_called()

    remove_queue(conv.id)


@pytest.mark.asyncio
async def test_always_mode_triggers():
    conv = await queries.create_conversation("test")
    await queries.create_message(conv.id, "user", "Any message")

    key = await queries.create_api_key(ApiKey(provider="openai", key_encrypted="encrypted"))
    config = LLMConfig(name="claude", provider="openai", model="gpt-4o",
                       participation_mode="always", api_key_id=key.id)
    await queries.create_llm_config(config)

    queue = get_or_create_queue(conv.id)

    with patch("app.orchestrator._run_llm_generation") as mock_run:
        mock_run.return_value = None
        await orchestrate_llm_responses(conv.id, queue, "Any message")
        mock_run.assert_called_once()

    remove_queue(conv.id)
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_orchestrator.py -v
```

Expected: 3 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_orchestrator.py
git commit -m "test: add orchestrator integration tests"
```

---

### Task 24: Final wiring and smoke test

- [ ] **Step 1: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS (~27 tests)

- [ ] **Step 2: Start the dev server and verify**

```bash
python run.py
```

Expected: Server starts on http://127.0.0.1:8000

- [ ] **Step 3: Add a conftest.py for shared fixtures**

Create `tests/conftest.py`:

```python
import pytest
from app.db.migrations import migrate
from app.db import queries

TEST_DB = ":memory:"


@pytest.fixture(autouse=True)
async def setup_db():
    queries.DB_PATH = TEST_DB
    await migrate(TEST_DB)
    yield
```

Then update test files to remove the duplicated `setup` fixture (already using TEST_DB).

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "chore: add shared test fixtures"
```

---

## Verification Checklist

Before marking implementation complete:

- [ ] `python -m pytest tests/ -v` — all tests green
- [ ] `python run.py` — server starts on :8000
- [ ] Browser: `http://127.0.0.1:8000` loads the chat UI in Chinese
- [ ] Browser: Create a new conversation
- [ ] Browser: Add an API key via Settings
- [ ] Browser: Add an LLM config via Settings
- [ ] Browser: Send a message @mentioning the LLM — see response
- [ ] Browser: Switch language to English — UI updates
- [ ] Browser: Switch back to Chinese — UI updates
