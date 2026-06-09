import os
import aiosqlite
from typing import Optional
from app.db.models import Conversation, Message, LLMConfig, Agent, ApiKey
from app.utils import get_base_dir

DB_PATH = os.path.join(get_base_dir(), "chat.db")


def _row_to_conversation(row: tuple) -> Conversation:
    return Conversation(id=row[0], title=row[1], created_at=row[2], updated_at=row[3])


def _row_to_message(row: tuple) -> Message:
    return Message(id=row[0], conversation_id=row[1], role=row[2],
                   llm_config_id=row[3], content=row[4], created_at=row[5],
                   agent_id=row[6] if len(row) > 6 else None)


def _row_to_llm_config(row: tuple) -> LLMConfig:
    return LLMConfig(id=row[0], provider=row[2], model=row[3],
                     api_key_id=row[4], max_response_chars=row[7],
                     is_title_generator=bool(row[10]) if len(row) > 10 else False,
                     created_at=row[9])


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


async def delete_conversation(conversation_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        await db.commit()


async def update_conversation_title(conversation_id: int, title: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
            (title, conversation_id),
        )
        await db.commit()


# --- Messages ---

async def create_message(conversation_id: int, role: str, content: str,
                         llm_config_id: Optional[int] = None,
                         agent_id: Optional[int] = None) -> Message:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO messages (conversation_id, role, content, llm_config_id, agent_id) VALUES (?, ?, ?, ?, ?)",
            (conversation_id, role, content, llm_config_id, agent_id),
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
            """INSERT INTO llm_configs (provider, model, api_key_id,
               max_response_chars, is_title_generator)
               VALUES (?, ?, ?, ?, ?)""",
            (config.provider, config.model, config.api_key_id,
             config.max_response_chars, int(config.is_title_generator)),
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
            """UPDATE llm_configs SET provider=?, model=?, api_key_id=?,
               max_response_chars=?, is_title_generator=?
               WHERE id=?""",
            (config.provider, config.model, config.api_key_id,
             config.max_response_chars, int(config.is_title_generator), config.id),
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


# --- Agents ---

def _row_to_agent(row: tuple) -> Agent:
    return Agent(id=row[0], name=row[1], llm_config_id=row[2],
                 system_prompt=row[3], style_preset=row[4],
                 participation_mode=row[5], probability=row[6],
                 created_at=row[7],
                 avatar_index=row[8] if len(row) > 8 else 0)


async def create_agent(agent: Agent) -> Agent:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO agents (name, llm_config_id, system_prompt, style_preset,
               participation_mode, probability, avatar_index)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (agent.name, agent.llm_config_id, agent.system_prompt,
             agent.style_preset, agent.participation_mode, agent.probability,
             agent.avatar_index),
        )
        await db.commit()
        row = await db.execute("SELECT * FROM agents WHERE id = ?", (cursor.lastrowid,))
        r = await row.fetchone()
        return _row_to_agent(r)


async def list_agents() -> list[Agent]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM agents ORDER BY created_at ASC")
        rows = await cursor.fetchall()
        return [_row_to_agent(r) for r in rows]


async def get_agent(agent_id: int) -> Optional[Agent]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = await cursor.fetchone()
        return _row_to_agent(row) if row else None


async def update_agent(agent: Agent) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE agents SET name=?, llm_config_id=?, system_prompt=?,
               style_preset=?, participation_mode=?, probability=?,
               avatar_index=?
               WHERE id=?""",
            (agent.name, agent.llm_config_id, agent.system_prompt,
             agent.style_preset, agent.participation_mode, agent.probability,
             agent.avatar_index, agent.id),
        )
        await db.commit()


async def delete_agent(agent_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        await db.commit()


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
