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
        cursor = await db.execute(
            "INSERT INTO conversations (title) VALUES (?)", (title,)
        )
        await db.commit()
        row = await db.execute("SELECT * FROM conversations WHERE id = ?", (cursor.lastrowid,))
        r = await row.fetchone()
        return _row_to_conversation(r)


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
        return _row_to_message(r)


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
