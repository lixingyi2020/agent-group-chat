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
    name TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT 'openai',
    model TEXT NOT NULL DEFAULT '',
    api_key_id INTEGER,
    participation_mode TEXT NOT NULL DEFAULT 'mention_only',
    probability REAL NOT NULL DEFAULT 0.3,
    max_response_chars INTEGER NOT NULL DEFAULT 200,
    system_prompt TEXT,
    is_title_generator INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    llm_config_id INTEGER NOT NULL,
    system_prompt TEXT NOT NULL DEFAULT '',
    style_preset TEXT NOT NULL DEFAULT 'custom',
    participation_mode TEXT NOT NULL DEFAULT 'mention_only',
    probability REAL NOT NULL DEFAULT 0.3,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (llm_config_id) REFERENCES llm_configs(id) ON DELETE CASCADE
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
        # Add is_title_generator column to existing databases
        try:
            await db.execute("ALTER TABLE llm_configs ADD COLUMN is_title_generator INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass  # Column already exists

        # Add agent_id column to messages (nullable, for backwards compat)
        try:
            await db.execute("ALTER TABLE messages ADD COLUMN agent_id INTEGER REFERENCES agents(id) ON DELETE SET NULL")
        except Exception:
            pass

        # Auto-migrate: create agents from existing LLM configs (only if agents table is empty)
        cursor = await db.execute("SELECT COUNT(*) FROM agents")
        agent_count = (await cursor.fetchone())[0]
        if agent_count == 0:
            cursor = await db.execute(
                "SELECT id, name, system_prompt, participation_mode, probability FROM llm_configs"
            )
            configs = await cursor.fetchall()
            for row in configs:
                config_id, name, system_prompt, participation_mode, probability = row
                await db.execute(
                    """INSERT OR IGNORE INTO agents
                       (name, llm_config_id, system_prompt, participation_mode, probability, style_preset)
                       VALUES (?, ?, ?, ?, ?, 'custom')""",
                    (name or f"Agent-{config_id}", config_id,
                     system_prompt or "", participation_mode or "mention_only",
                     probability if probability is not None else 0.3),
                )
        await db.commit()
