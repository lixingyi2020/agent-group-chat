import pytest
import tempfile
import os
import aiosqlite
from app.db.migrations import migrate


@pytest.mark.asyncio
async def test_agents_table_created():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        await migrate(path)
        async with aiosqlite.connect(path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='agents'"
            )
            assert await cursor.fetchone() is not None
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_auto_migration_creates_agents():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        async with aiosqlite.connect(path) as db:
            # Simulate a pre-existing database with llm_configs
            await db.execute("""CREATE TABLE llm_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT 'openai',
                model TEXT NOT NULL DEFAULT '',
                api_key_id INTEGER,
                participation_mode TEXT NOT NULL DEFAULT 'mention_only',
                probability REAL NOT NULL DEFAULT 0.3,
                max_response_chars INTEGER NOT NULL DEFAULT 200,
                system_prompt TEXT,
                is_title_generator INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )""")
            await db.execute("CREATE TABLE api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT, key_encrypted TEXT, created_at TEXT DEFAULT (datetime('now')))")
            await db.execute("CREATE TABLE conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')))")
            await db.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER, role TEXT, llm_config_id INTEGER, content TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now')))")
            await db.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT DEFAULT '')")
            await db.execute("INSERT INTO api_keys (id, provider, key_encrypted) VALUES (1, 'openai', 'enc')")
            await db.execute("INSERT INTO llm_configs (id, name, provider, model, system_prompt, participation_mode, probability, api_key_id) VALUES (1, 'Claude', 'anthropic', 'claude-opus', 'You are helpful', 'mention_only', 0.5, 1)")
            await db.commit()

        await migrate(path)

        async with aiosqlite.connect(path) as db:
            cursor = await db.execute("SELECT * FROM agents")
            agents = await cursor.fetchall()
            assert len(agents) == 1
            agent = agents[0]
            assert agent[1] == "Claude"  # name (index 1)
            assert agent[2] == 1  # llm_config_id (index 2)
            assert agent[3] == "You are helpful"  # system_prompt (index 3)
            assert agent[4] == "custom"  # style_preset (index 4)
            assert agent[5] == "mention_only"  # participation_mode (index 5)
            assert agent[6] == 0.5  # probability (index 6)

            # Check messages.agent_id column exists
            cursor = await db.execute("PRAGMA table_info(messages)")
            cols = {row[1] for row in await cursor.fetchall()}
            assert "agent_id" in cols
    finally:
        os.unlink(path)
