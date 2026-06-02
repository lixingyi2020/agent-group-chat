# AI Agent Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce an Agent abstraction between LLM Configs (technical layer) and the group chat (participant layer), so one LLM can power multiple agents with distinct names, personalities, and language styles.

**Architecture:** Add `agents` table with FK to `llm_configs`. Move participant fields (name, system_prompt, participation_mode, probability) from LLM Config to Agent. Update orchestrator to iterate agents (resolving LLM config from agent). Auto-migrate existing configs to create a default agent per LLM. Add agent CRUD to Settings page. Update chat UI to show agents instead of LLMs.

**Tech Stack:** Python FastAPI + HTMX + Jinja2 + SQLite + aiosqlite (same as existing)

---

### Task 1: Add Agent dataclass and update existing models

**Files:**
- Modify: `app/db/models.py`
- Create: `tests/test_agent_models.py`

- [ ] **Step 1: Add Agent dataclass to models.py**

```python
# After the LLMConfig dataclass (line 36), add:

@dataclass
class Agent:
    id: Optional[int] = None
    name: str = ""
    llm_config_id: int = 0
    system_prompt: str = ""
    style_preset: str = "custom"  # "brief", "rigorous", "witty", "custom"
    participation_mode: str = "mention_only"
    probability: float = 0.3
    created_at: str = ""
```

- [ ] **Step 2: Remove agent-related fields from LLMConfig**

Remove `name`, `system_prompt`, `participation_mode`, `probability` from the `LLMConfig` dataclass. The updated class:

```python
@dataclass
class LLMConfig:
    id: Optional[int] = None
    provider: str = "openai"
    model: str = ""
    api_key_id: Optional[int] = None
    max_response_chars: int = 200
    is_title_generator: bool = False
    created_at: str = ""
```

- [ ] **Step 3: Add agent_id to Message dataclass**

```python
@dataclass
class Message:
    id: Optional[int] = None
    conversation_id: int = 0
    role: str = "user"  # "user", "llm", "system"
    llm_config_id: Optional[int] = None
    agent_id: Optional[int] = None
    content: str = ""
    created_at: str = ""
```

- [ ] **Step 4: Write model unit tests**

Create `tests/test_agent_models.py`:

```python
from app.db.models import Agent, LLMConfig, Message


def test_agent_defaults():
    a = Agent()
    assert a.name == ""
    assert a.style_preset == "custom"
    assert a.participation_mode == "mention_only"
    assert a.probability == 0.3


def test_agent_create_with_fields():
    a = Agent(name="小助手", llm_config_id=1, system_prompt="Be helpful",
              style_preset="brief", participation_mode="always", probability=1.0)
    assert a.name == "小助手"
    assert a.llm_config_id == 1
    assert a.style_preset == "brief"


def test_llm_config_no_longer_has_name():
    c = LLMConfig(provider="openai", model="gpt-4o")
    assert not hasattr(c, 'name') or c.name == ""


def test_message_has_agent_id():
    m = Message(agent_id=5)
    assert m.agent_id == 5
    assert m.llm_config_id is None
```

- [ ] **Step 5: Run tests, verify failure on non-existent Agent import**

Run: `pytest tests/test_agent_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'Agent'`

- [ ] **Step 6: Commit**

```bash
git add app/db/models.py tests/test_agent_models.py
git commit -m "feat: add Agent dataclass, slim LLMConfig to technical fields, add agent_id to Message"
```

---

### Task 2: Database migration — create agents table and auto-migrate

**Files:**
- Modify: `app/db/migrations.py`
- Create: `tests/test_agent_migration.py`

- [ ] **Step 1: Add agents table and ALTER TABLE to migrations.py**

In `SCHEMA_SQL`, add after `llm_configs` table:

```sql
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
```

- [ ] **Step 2: Add auto-migration logic at end of `migrate()` function**

After the existing `is_title_generator` ALTER TABLE, add:

```python
        # Auto-migrate: create agents from existing LLM configs
        try:
            await db.execute("ALTER TABLE messages ADD COLUMN agent_id INTEGER REFERENCES agents(id) ON DELETE SET NULL")
        except Exception:
            pass

        # Check if agents table was newly created (empty) and llm_configs have data to migrate
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
                     probability or 0.3),
                )
```

- [ ] **Step 3: Write migration test**

Create `tests/test_agent_migration.py`:

```python
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
            assert agent[1] == "Claude"  # name
            assert agent[2] == 1  # llm_config_id
            assert agent[3] == "You are helpful"  # system_prompt
            assert agent[5] == "mention_only"  # participation_mode
            assert agent[6] == 0.5  # probability

            # Check messages.agent_id column exists
            cursor = await db.execute("PRAGMA table_info(messages)")
            cols = {row[1] for row in await cursor.fetchall()}
            assert "agent_id" in cols
    finally:
        os.unlink(path)
```

- [ ] **Step 4: Run migration tests**

Run: `pytest tests/test_agent_migration.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add app/db/migrations.py tests/test_agent_migration.py
git commit -m "feat: add agents table migration with auto-migration from llm_configs"
```

---

### Task 3: Agent CRUD queries + update existing queries

**Files:**
- Modify: `app/db/queries.py`
- Create: `tests/test_agent_queries.py`

- [ ] **Step 1: Add Agent CRUD functions to queries.py**

Add after the LLM Config CRUD section (before `# --- API Keys ---`):

```python
# --- Agents ---

def _row_to_agent(row: tuple) -> Agent:
    return Agent(id=row[0], name=row[1], llm_config_id=row[2],
                 system_prompt=row[3], style_preset=row[4],
                 participation_mode=row[5], probability=row[6],
                 created_at=row[7])


async def create_agent(agent: Agent) -> Agent:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO agents (name, llm_config_id, system_prompt, style_preset,
               participation_mode, probability)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (agent.name, agent.llm_config_id, agent.system_prompt,
             agent.style_preset, agent.participation_mode, agent.probability),
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
               style_preset=?, participation_mode=?, probability=?
               WHERE id=?""",
            (agent.name, agent.llm_config_id, agent.system_prompt,
             agent.style_preset, agent.participation_mode, agent.probability,
             agent.id),
        )
        await db.commit()


async def delete_agent(agent_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        await db.commit()
```

- [ ] **Step 2: Update `create_message` to accept optional `agent_id`**

```python
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
```

- [ ] **Step 3: Update `_row_to_message` to handle `agent_id` column**

```python
def _row_to_message(row: tuple) -> Message:
    return Message(id=row[0], conversation_id=row[1], role=row[2],
                   llm_config_id=row[3], content=row[4], created_at=row[5],
                   agent_id=row[6] if len(row) > 6 else None)
```

- [ ] **Step 4: Update `_row_to_llm_config` to match the new schema (no name, system_prompt, participation_mode, probability)**

Replace the existing `_row_to_llm_config`:

```python
def _row_to_llm_config(row: tuple) -> LLMConfig:
    return LLMConfig(id=row[0], provider=row[2], model=row[3],
                     api_key_id=row[4], max_response_chars=row[7],
                     is_title_generator=bool(row[10]) if len(row) > 10 else False,
                     created_at=row[9])
```

Note: column indices shifted. The query still does `SELECT *`, so:
- 0:id, 1:name (old — skip), 2:provider, 3:model, 4:api_key_id, 5:participation_mode(old — skip), 6:probability(old — skip), 7:max_response_chars, 8:system_prompt(old — skip), 9:created_at, 10:is_title_generator

**Wait — since we haven't actually removed columns from the DB (SQLite can't drop columns easily), the old columns remain. `SELECT *` still returns all columns including the old ones. We should continue reading from the same positions as before, just skip the fields we no longer need in the dataclass.**

Actually, let's keep it simpler. We won't drop columns from the DB (SQLite limitation). The old columns stay but are ignored by the dataclass. The `_row_to_llm_config` stays mostly the same but we remove `name` from the dataclass (so keep the current column mapping, just stop passing the fields we removed):

```python
def _row_to_llm_config(row: tuple) -> LLMConfig:
    return LLMConfig(id=row[0], provider=row[2], model=row[3],
                     api_key_id=row[4], max_response_chars=row[7],
                     is_title_generator=bool(row[10]) if len(row) > 10 else False,
                     created_at=row[9])
```

- [ ] **Step 5: Update `create_llm_config` to not need name/participation_mode/probability/system_prompt**

```python
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
```

- [ ] **Step 6: Update `update_llm_config` similarly**

```python
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
```

- [ ] **Step 7: Write agent query tests**

Create `tests/test_agent_queries.py`:

```python
import pytest
from app.db import queries
from app.db.models import Agent, LLMConfig, ApiKey


@pytest.mark.asyncio
async def test_create_and_list_agents(db):
    key = await queries.create_api_key(ApiKey(provider="openai", key_encrypted="enc"))
    config = LLMConfig(provider="openai", model="gpt-4o", api_key_id=key.id)
    config = await queries.create_llm_config(config)

    agent = Agent(name="test-agent", llm_config_id=config.id,
                  system_prompt="Be helpful", style_preset="brief",
                  participation_mode="always", probability=0.8)
    created = await queries.create_agent(agent)
    assert created.id is not None
    assert created.name == "test-agent"
    assert created.style_preset == "brief"

    agents = await queries.list_agents()
    assert len(agents) == 1


@pytest.mark.asyncio
async def test_get_and_update_agent(db):
    key = await queries.create_api_key(ApiKey(provider="openai", key_encrypted="enc"))
    config = await queries.create_llm_config(LLMConfig(provider="openai", model="gpt-4o", api_key_id=key.id))
    agent = await queries.create_agent(Agent(name="test", llm_config_id=config.id, system_prompt="original"))

    fetched = await queries.get_agent(agent.id)
    assert fetched.name == "test"
    assert fetched.system_prompt == "original"

    fetched.system_prompt = "updated"
    fetched.style_preset = "witty"
    await queries.update_agent(fetched)

    updated = await queries.get_agent(agent.id)
    assert updated.system_prompt == "updated"
    assert updated.style_preset == "witty"


@pytest.mark.asyncio
async def test_delete_agent(db):
    key = await queries.create_api_key(ApiKey(provider="openai", key_encrypted="enc"))
    config = await queries.create_llm_config(LLMConfig(provider="openai", model="gpt-4o", api_key_id=key.id))
    agent = await queries.create_agent(Agent(name="to-delete", llm_config_id=config.id))

    await queries.delete_agent(agent.id)
    assert await queries.get_agent(agent.id) is None


@pytest.mark.asyncio
async def test_create_message_with_agent_id(db):
    from app.db.models import Conversation
    conv = await queries.create_conversation("test")
    msg = await queries.create_message(conv.id, "llm", "Hello", agent_id=5)
    assert msg.agent_id == 5
```

- [ ] **Step 8: Run agent query tests**

Run: `pytest tests/test_agent_queries.py -v`
Expected: 4 PASS

- [ ] **Step 9: Commit**

```bash
git add app/db/queries.py tests/test_agent_queries.py
git commit -m "feat: add Agent CRUD queries, update message/llm_config queries for new schema"
```

---

### Task 4: Orchestrator — use Agents instead of LLMConfigs

**Files:**
- Modify: `app/orchestrator.py`
- Modify: `tests/test_participation.py`
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Update `should_respond` to accept an Agent instead of LLMConfig**

```python
from app.db.models import Agent

def should_respond(agent: Agent, message_text: str, is_self: bool = False,
                   mention_names: list[str] | None = None) -> bool:
    if mention_names is None:
        mention_names = extract_mentions(message_text)

    everyone_mentioned = bool(EVERYONE_ALIASES & set(mention_names))
    if everyone_mentioned:
        return True

    specific_mentions = [n for n in mention_names if n not in EVERYONE_ALIASES]
    if specific_mentions:
        return agent.name in specific_mentions

    if is_self:
        return False

    if agent.participation_mode == "always":
        return True

    if agent.participation_mode == "probabilistic":
        return random.random() < agent.probability

    return False
```

- [ ] **Step 2: Update `_run_llm_generation` to accept Agent, resolve LLMConfig from it**

```python
async def _run_llm_generation(
    agent: Agent,
    conversation_id: int,
    event_queue: asyncio.Queue,
    depth: int = 0,
) -> Optional[Message]:
    config = await queries.get_llm_config(agent.llm_config_id)
    if not config:
        print(f"[Agent] {agent.name}: LLM config {agent.llm_config_id} not found", flush=True)
        await event_queue.put({
            "type": "llm-error",
            "llm_config_id": agent.llm_config_id,
            "error": f"LLM config not found for agent {agent.name}",
            "retryable": False,
        })
        return None

    provider = get_provider(config.provider)
    request = None
    print(f"[Agent] {agent.name} ({config.provider}/{config.model}) starting...", flush=True)
    try:
        api_key_record = await queries.get_api_key(config.api_key_id)
        if not api_key_record:
            print(f"[Agent] {agent.name}: No API key found (id={config.api_key_id})", flush=True)
            raise ProviderError(f"No API key configured for {config.provider}", status_code=0, retryable=False)

        api_key = decrypt(api_key_record.key_encrypted)
        messages = await _build_messages(conversation_id)

        if config.provider == "deepseek":
            max_tokens = max(config.max_response_chars * 4, 2000)
        else:
            max_tokens = config.max_response_chars

        request = LLMRequest(
            model=config.model,
            api_key=api_key,
            system_prompt=agent.system_prompt,
            messages=messages,
            max_tokens=max_tokens,
        )

        full_content = ""

        async for token in provider.generate_stream(request):
            full_content += token
            await event_queue.put({
                "type": "token",
                "llm_config_id": config.id,
                "token": token,
            })
        print(f"[Agent] {agent.name}: stream complete, {len(full_content)} chars", flush=True)

        if not full_content.strip():
            print(f"[Agent] {agent.name}: empty response, skipping save", flush=True)
            await event_queue.put({
                "type": "llm-error",
                "llm_config_id": config.id,
                "error": "Empty response (possibly all tokens consumed by reasoning)",
                "retryable": False,
            })
            return None

        message = await queries.create_message(
            conversation_id, "llm", full_content, config.id, agent_id=agent.id
        )

        await event_queue.put({
            "type": "complete",
            "llm_config_id": config.id,
            "message_id": message.id,
            "content": full_content,
        })
        print(f"[Agent] {agent.name}: complete event pushed. DB message id={message.id}", flush=True)

        # LLM-to-LLM mentions: now match against agent names
        if depth < MAX_CHAIN_DEPTH:
            mentions = extract_mentions(full_content)
            if mentions:
                all_agents = await queries.list_agents()
                for mentioned_agent in all_agents:
                    if mentioned_agent.name in mentions and mentioned_agent.id != agent.id:
                        await _run_llm_generation(
                            mentioned_agent, conversation_id, event_queue, depth + 1
                        )

        return message

    except ProviderError as e:
        print(f"[Agent] {agent.name}: ProviderError: {e} (retryable={e.retryable})", flush=True)
        if e.retryable and request is not None:
            try:
                response = await with_retries(provider.generate, request)
                full_content = response.content
                await event_queue.put({"type": "token", "llm_config_id": config.id, "token": full_content})
                message = await queries.create_message(conversation_id, "llm", full_content, config.id, agent_id=agent.id)
                await event_queue.put({"type": "complete", "llm_config_id": config.id, "message_id": message.id, "content": full_content})
                return message
            except Exception as retry_err:
                logger.warning(f"Retry failed for {agent.name}: {retry_err}")
        await event_queue.put({
            "type": "llm-error",
            "llm_config_id": config.id,
            "error": str(e),
            "retryable": e.retryable,
        })
        return None
    except Exception as e:
        logger.exception(f"Unexpected error for agent {agent.name}: {e}")
        await event_queue.put({
            "type": "llm-error",
            "llm_config_id": config.id,
            "error": str(e),
            "retryable": False,
        })
        return None
```

- [ ] **Step 3: Update `orchestrate_llm_responses` to iterate agents**

```python
async def orchestrate_llm_responses(
    conversation_id: int,
    event_queue: asyncio.Queue,
    triggering_message_text: str,
    triggering_agent_id: Optional[int] = None,
    depth: int = 0,
) -> None:
    agents = await queries.list_agents()
    mention_names = extract_mentions(triggering_message_text)

    tasks_to_run = []
    for agent in agents:
        is_self = agent.id == triggering_agent_id
        if should_respond(agent, triggering_message_text, is_self=is_self, mention_names=mention_names):
            tasks_to_run.append(agent)

    print(f"[Orchestrator] Triggering {len(tasks_to_run)} agents: {[a.name for a in tasks_to_run]}", flush=True)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def _run_with_limit(agent: Agent):
        async with semaphore:
            await _run_llm_generation(agent, conversation_id, event_queue, depth)

    await asyncio.gather(*[_run_with_limit(a) for a in tasks_to_run])
```

- [ ] **Step 4: Update `_auto_title` to find agent of the title-generator LLM**

In `fragments.py`, update the `_auto_title` function to look up the title-generator LLM config and find an agent for it:

```python
async def _auto_title(conversation_id: int, first_message: str):
    """Generate a short title using an agent of the title-generator LLM."""
    try:
        from app.crypto import decrypt
        from app.providers import get_provider
        from app.providers.base import LLMRequest

        configs = await queries.list_llm_configs()
        title_config = next((c for c in configs if c.is_title_generator), None)
        if not title_config:
            title_config = configs[0] if configs else None
        if not title_config:
            return

        # Find any agent for this LLM config
        agents = await queries.list_agents()
        title_agent = next((a for a in agents if a.llm_config_id == title_config.id), None)
        if not title_agent:
            print(f"[AutoTitle] No agent found for title LLM config {title_config.id}", flush=True)
            return

        print(f"[AutoTitle] Starting for conv {conversation_id} with agent {title_agent.name}", flush=True)

        key_record = await queries.get_api_key(title_config.api_key_id)
        if not key_record:
            return
        api_key = decrypt(key_record.key_encrypted)

        provider = get_provider(title_config.provider)
        title_max_tokens = 2000 if title_config.provider == "deepseek" else 30

        request = LLMRequest(
            model=title_config.model,
            api_key=api_key,
            system_prompt="Generate a SHORT title (max 6 words) summarizing the user's message. Reply with ONLY the title, no quotes.",
            messages=[{"role": "user", "content": first_message}],
            max_tokens=title_max_tokens,
        )
        response = await provider.generate(request)
        title = response.content.strip().strip('"').strip("'")[:50]
        print(f"[AutoTitle] Response: '{response.content}' -> title: '{title}'", flush=True)
        if title:
            await queries.update_conversation_title(conversation_id, title)
            print(f"[AutoTitle] Title saved: {title}", flush=True)
    except Exception as e:
        print(f"[AutoTitle] Failed: {type(e).__name__}: {e}", flush=True)
```

- [ ] **Step 5: Update imports in orchestrator.py**

```python
from app.db.models import Agent
```

Remove unused import of `LLMConfig` (unless still used elsewhere).

- [ ] **Step 6: Update participation tests to use Agent**

In `tests/test_participation.py`, replace all `LLMConfig(name=...)` with `Agent(name=...)`:

```python
from app.db.models import Agent
from app.orchestrator import should_respond, extract_mentions


def test_extract_mentions():
    assert extract_mentions("Hello @claude what do you think?") == ["claude"]
    assert extract_mentions("@claude and @gpt help me") == ["claude", "gpt"]
    assert extract_mentions("No mentions here") == []
    assert extract_mentions("@mention-with-dashes") == ["mention-with-dashes"]


def test_mention_always_responds():
    agent = Agent(name="claude", participation_mode="mention_only")
    assert should_respond(agent, "Hey @claude", mention_names=["claude"]) is True


def test_always_mode_responds():
    agent = Agent(name="claude", participation_mode="always")
    assert should_respond(agent, "Just a normal message") is True


def test_mention_only_skips_without_mention():
    agent = Agent(name="claude", participation_mode="mention_only")
    assert should_respond(agent, "Just a normal message") is False


def test_probabilistic_0_never_responds():
    agent = Agent(name="claude", participation_mode="probabilistic", probability=0.0)
    responses = [should_respond(agent, "msg") for _ in range(100)]
    assert all(r is False for r in responses)


def test_probabilistic_1_always_responds():
    agent = Agent(name="claude", participation_mode="probabilistic", probability=1.0)
    responses = [should_respond(agent, "msg") for _ in range(100)]
    assert all(r is True for r in responses)


def test_self_reply_prevented():
    agent = Agent(name="claude", participation_mode="always")
    assert should_respond(agent, "my own message", is_self=True) is False


def test_self_reply_allowed_when_mentioned():
    agent = Agent(name="claude", participation_mode="always")
    assert should_respond(agent, "I agree with @claude", is_self=True, mention_names=["claude"]) is True


def test_everyone_triggers_all():
    agent = Agent(name="claude", participation_mode="mention_only")
    assert should_respond(agent, "Hey @Everyone", mention_names=["Everyone"]) is True
    assert should_respond(agent, "Hey @所有AI", mention_names=["所有AI"]) is True


def test_everyone_overrides_self_reply():
    agent = Agent(name="claude", participation_mode="always")
    assert should_respond(agent, "@Everyone what now?", is_self=True, mention_names=["Everyone"]) is True


def test_specific_mention_blocks_others():
    claude = Agent(name="claude", participation_mode="mention_only")
    gpt = Agent(name="gpt", participation_mode="always")
    assert should_respond(claude, "Hey @claude", mention_names=["claude"]) is True
    assert should_respond(gpt, "Hey @claude", mention_names=["claude"]) is False


def test_mixed_mentions_only_mentioned_respond():
    claude = Agent(name="claude", participation_mode="mention_only")
    gpt = Agent(name="gpt", participation_mode="mention_only")
    other = Agent(name="other", participation_mode="always")
    assert should_respond(claude, "@claude @gpt help", mention_names=["claude", "gpt"]) is True
    assert should_respond(gpt, "@claude @gpt help", mention_names=["claude", "gpt"]) is True
    assert should_respond(other, "@claude @gpt help", mention_names=["claude", "gpt"]) is False
```

- [ ] **Step 7: Update orchestrator tests to create agents**

In `tests/test_orchestrator.py`, update to create agents instead of LLM configs for participation:

```python
import pytest
from unittest.mock import patch
from app.db.models import LLMConfig, ApiKey, Agent
from app.db import queries
from app.orchestrator import orchestrate_llm_responses
from app.routes.stream import get_or_create_queue, remove_queue


@pytest.mark.asyncio
async def test_orchestrate_with_mention_only_agent(db):
    conv = await queries.create_conversation("test")
    await queries.create_message(conv.id, "user", "Hello @claude")

    key = await queries.create_api_key(ApiKey(provider="openai", key_encrypted="encrypted"))
    config = await queries.create_llm_config(LLMConfig(provider="openai", model="gpt-4o", api_key_id=key.id))
    await queries.create_agent(Agent(name="claude", llm_config_id=config.id, participation_mode="mention_only"))

    queue = get_or_create_queue(conv.id)

    with patch("app.orchestrator._run_llm_generation") as mock_run:
        mock_run.return_value = None
        await orchestrate_llm_responses(conv.id, queue, "Hello @claude")

    remove_queue(conv.id)


@pytest.mark.asyncio
async def test_mention_only_skips_without_mention(db):
    conv = await queries.create_conversation("test")
    await queries.create_message(conv.id, "user", "Just a normal message")

    key = await queries.create_api_key(ApiKey(provider="openai", key_encrypted="encrypted"))
    config = await queries.create_llm_config(LLMConfig(provider="openai", model="gpt-4o", api_key_id=key.id))
    await queries.create_agent(Agent(name="claude", llm_config_id=config.id, participation_mode="mention_only"))

    queue = get_or_create_queue(conv.id)

    with patch("app.orchestrator._run_llm_generation") as mock_run:
        await orchestrate_llm_responses(conv.id, queue, "Just a normal message")
        mock_run.assert_not_called()

    remove_queue(conv.id)


@pytest.mark.asyncio
async def test_always_mode_triggers(db):
    conv = await queries.create_conversation("test")
    await queries.create_message(conv.id, "user", "Any message")

    key = await queries.create_api_key(ApiKey(provider="openai", key_encrypted="encrypted"))
    config = await queries.create_llm_config(LLMConfig(provider="openai", model="gpt-4o", api_key_id=key.id))
    await queries.create_agent(Agent(name="claude", llm_config_id=config.id, participation_mode="always"))

    queue = get_or_create_queue(conv.id)

    with patch("app.orchestrator._run_llm_generation") as mock_run:
        mock_run.return_value = None
        await orchestrate_llm_responses(conv.id, queue, "Any message")
        mock_run.assert_called_once()

    remove_queue(conv.id)
```

- [ ] **Step 8: Run all orchestrator and participation tests**

Run: `pytest tests/test_participation.py tests/test_orchestrator.py -v`
Expected: 14 PASS (11 participation + 3 orchestrator)

- [ ] **Step 9: Commit**

```bash
git add app/orchestrator.py tests/test_participation.py tests/test_orchestrator.py
git commit -m "refactor: update orchestrator to use Agents instead of LLMConfigs"
```

---

### Task 5: Agent CRUD routes + Settings page update

**Files:**
- Modify: `app/routes/fragments.py`
- Create: `app/templates/fragments/agents.html`
- Modify: `app/templates/pages/settings.html`
- Modify: `app/i18n/en.py`, `app/i18n/zh.py`
- Create: `tests/test_agent_routes.py`

- [ ] **Step 1: Add i18n strings**

In `app/i18n/en.py`, add:
```python
    "agents": "AI Agents",
    "add_agent": "Add Agent",
    "style_preset": "Style",
    "style_brief": "Brief",
    "style_rigorous": "Rigorous",
    "style_witty": "Witty",
    "style_custom": "Custom",
    "base_llm": "Base LLM",
```

In `app/i18n/zh.py`, add:
```python
    "agents": "智能助手",
    "add_agent": "添加助手",
    "style_preset": "风格",
    "style_brief": "简短",
    "style_rigorous": "严谨",
    "style_witty": "风趣",
    "style_custom": "自定义",
    "base_llm": "基础 LLM",
```

- [ ] **Step 2: Create agents.html fragment template**

Create `app/templates/fragments/agents.html`:

```html
<div style="padding: 24px; max-width: 600px;">
    <h2 style="margin-bottom: 16px;">{{ strings.agents }}</h2>

    {% for agent in agents %}
    <div id="agent-{{ agent.id }}" class="llm-config-card">
        <!-- View mode -->
        <div id="agent-view-{{ agent.id }}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <strong>{{ agent.name }}</strong>
                <span style="font-size: 11px; color: var(--text-muted);">
                    {{ strings.base_llm }}: {{ llm_map[agent.llm_config_id].provider }} / {{ llm_map[agent.llm_config_id].model }}
                </span>
            </div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">
                {{ strings.style_preset }}: {{ agent.style_preset }}
                &nbsp;|&nbsp; {{ strings.participation_mode }}: {{ agent.participation_mode }}
            </div>
            <div style="display: flex; gap: 8px;">
                <button class="btn-secondary" style="width: auto;"
                        onclick="toggleEditAgent({{ agent.id }})">✎ Edit</button>
                <button class="btn-secondary" style="width: auto;"
                        hx-delete="/fragments/agents/{{ agent.id }}"
                        hx-target="#agent-{{ agent.id }}"
                        hx-swap="outerHTML">{{ strings.delete }}</button>
            </div>
        </div>
        <!-- Edit mode -->
        <div id="agent-edit-{{ agent.id }}" style="display: none;">
            <form style="display: flex; flex-direction: column; gap: 8px;"
                  hx-put="/fragments/agents/{{ agent.id }}"
                  hx-target="#agent-{{ agent.id }}"
                  hx-swap="outerHTML">
                <input name="name" value="{{ agent.name }}" required
                       style="background: var(--bg-primary); border: 1px solid var(--border-color);
                              border-radius: 6px; padding: 6px 10px; color: var(--text-primary); font-size: 13px;">
                <select name="llm_config_id"
                        style="background: var(--bg-primary); border: 1px solid var(--border-color);
                               border-radius: 6px; padding: 6px 10px; color: var(--text-primary); font-size: 13px;">
                    {% for llm in llm_configs %}
                    <option value="{{ llm.id }}" {% if llm.id == agent.llm_config_id %}selected{% endif %}>
                        {{ llm.provider }} / {{ llm.model }}
                    </option>
                    {% endfor %}
                </select>
                <select name="style_preset" onchange="updateStylePrompt(this, {{ agent.id }})"
                        style="background: var(--bg-primary); border: 1px solid var(--border-color);
                               border-radius: 6px; padding: 6px 10px; color: var(--text-primary); font-size: 13px;">
                    <option value="brief" {% if agent.style_preset == 'brief' %}selected{% endif %}>{{ strings.style_brief }}</option>
                    <option value="rigorous" {% if agent.style_preset == 'rigorous' %}selected{% endif %}>{{ strings.style_rigorous }}</option>
                    <option value="witty" {% if agent.style_preset == 'witty' %}selected{% endif %}>{{ strings.style_witty }}</option>
                    <option value="custom" {% if agent.style_preset == 'custom' %}selected{% endif %}>{{ strings.style_custom }}</option>
                </select>
                <textarea name="system_prompt" id="agent-prompt-{{ agent.id }}" rows="3"
                          style="background: var(--bg-primary); border: 1px solid var(--border-color);
                                 border-radius: 6px; padding: 6px 10px; color: var(--text-primary); font-size: 12px;
                                 resize: vertical;">{{ agent.system_prompt }}</textarea>
                <select name="participation_mode"
                        style="background: var(--bg-primary); border: 1px solid var(--border-color);
                               border-radius: 6px; padding: 6px 10px; color: var(--text-primary); font-size: 13px;">
                    <option value="mention_only" {% if agent.participation_mode == 'mention_only' %}selected{% endif %}>{{ strings.mention_only }}</option>
                    <option value="always" {% if agent.participation_mode == 'always' %}selected{% endif %}>{{ strings.always }}</option>
                    <option value="probabilistic" {% if agent.participation_mode == 'probabilistic' %}selected{% endif %}>{{ strings.probabilistic }}</option>
                </select>
                <div style="display: flex; gap: 8px;">
                    <button class="btn-secondary" type="submit" style="width: auto;">{{ strings.save }}</button>
                    <button class="btn-secondary" type="button" style="width: auto;"
                            onclick="toggleEditAgent({{ agent.id }})">{{ strings.cancel }}</button>
                </div>
            </form>
        </div>
    </div>
    {% endfor %}

    <details style="margin-top: 16px;">
        <summary style="cursor: pointer; color: var(--accent-blue); font-size: 14px;">
            {{ strings.add_agent }}
        </summary>
        {% if llm_configs %}
        <form style="margin-top: 12px; display: flex; flex-direction: column; gap: 10px;"
              hx-post="/fragments/agents"
              hx-target="#agents-container">
            <input name="name" placeholder="{{ strings.name }}" required
                   style="background: var(--bg-tertiary); border: 1px solid var(--border-color);
                          border-radius: 6px; padding: 8px; color: var(--text-primary); font-size: 13px;">
            <select name="llm_config_id" required
                    style="background: var(--bg-tertiary); border: 1px solid var(--border-color);
                           border-radius: 6px; padding: 8px; color: var(--text-primary); font-size: 13px;">
                {% for llm in llm_configs %}
                <option value="{{ llm.id }}">{{ llm.provider }} / {{ llm.model }}</option>
                {% endfor %}
            </select>
            <select name="style_preset" onchange="updateNewStylePrompt(this)"
                    style="background: var(--bg-tertiary); border: 1px solid var(--border-color);
                           border-radius: 6px; padding: 8px; color: var(--text-primary); font-size: 13px;">
                <option value="brief">{{ strings.style_brief }}</option>
                <option value="rigorous">{{ strings.style_rigorous }}</option>
                <option value="witty">{{ strings.style_witty }}</option>
                <option value="custom">{{ strings.style_custom }}</option>
            </select>
            <textarea name="system_prompt" id="new-agent-prompt" rows="3" placeholder="{{ strings.system_prompt }}"
                      style="background: var(--bg-tertiary); border: 1px solid var(--border-color);
                             border-radius: 6px; padding: 8px; color: var(--text-primary); font-size: 12px;
                             resize: vertical;"></textarea>
            <select name="participation_mode" required
                    style="background: var(--bg-tertiary); border: 1px solid var(--border-color);
                           border-radius: 6px; padding: 8px; color: var(--text-primary); font-size: 13px;">
                <option value="mention_only">{{ strings.mention_only }}</option>
                <option value="always">{{ strings.always }}</option>
                <option value="probabilistic">{{ strings.probabilistic }}</option>
            </select>
            <button class="btn-secondary" type="submit">{{ strings.save }}</button>
        </form>
        {% else %}
        <div style="font-size: 13px; color: #f59e0b; padding: 12px 0;">
            No LLM configs yet. Add one above first.
        </div>
        {% endif %}
    </details>
</div>

<script>
const STYLE_PROMPTS = {
    brief: "{{ strings.style_brief }}",
    brief_prompt: "Reply concisely. Keep responses under 2-3 sentences. Get straight to the point.",
    rigorous: "{{ strings.style_rigorous }}",
    rigorous_prompt: "Reply with rigorous reasoning. Consider edge cases. Be precise and accurate.",
    witty: "{{ strings.style_witty }}",
    witty_prompt: "Reply with humor and wit. Use playful language and occasional jokes.",
    custom: "{{ strings.style_custom }}",
    custom_prompt: ""
};

function updateStylePrompt(select, agentId) {
    var textarea = document.getElementById('agent-prompt-' + agentId);
    var key = select.value + '_prompt';
    if (STYLE_PROMPTS[key] !== undefined) {
        textarea.value = STYLE_PROMPTS[key];
    }
}

function updateNewStylePrompt(select) {
    var textarea = document.getElementById('new-agent-prompt');
    var key = select.value + '_prompt';
    if (STYLE_PROMPTS[key] !== undefined) {
        textarea.value = STYLE_PROMPTS[key];
    }
}

function toggleEditAgent(id) {
    var view = document.getElementById('agent-view-' + id);
    var edit = document.getElementById('agent-edit-' + id);
    if (view.style.display === 'none') {
        view.style.display = '';
        edit.style.display = 'none';
    } else {
        view.style.display = 'none';
        edit.style.display = '';
    }
}
</script>
```

- [ ] **Step 3: Add Agent CRUD route handlers to fragments.py**

Add imports at top:
```python
from app.db.models import Agent
```

Add route handlers before the `# --- Settings ---` comment or after the LLM config routes:

```python
# --- Agent routes ---

@router.get("/fragments/agents", response_class=HTMLResponse)
async def fragment_agents(request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    agents = await queries.list_agents()
    llm_configs = await queries.list_llm_configs()
    llm_map = {c.id: c for c in llm_configs}
    return templates.TemplateResponse(
        request,
        "fragments/agents.html",
        {"request": request, "locale": locale, "strings": strings,
         "agents": agents, "llm_configs": llm_configs, "llm_map": llm_map},
    )


@router.post("/fragments/agents", response_class=HTMLResponse)
async def fragment_create_agent(
    request: Request,
    name: str = Form(...),
    llm_config_id: int = Form(...),
    system_prompt: str = Form(""),
    style_preset: str = Form("custom"),
    participation_mode: str = Form("mention_only"),
):
    agent = Agent(
        name=name, llm_config_id=llm_config_id,
        system_prompt=system_prompt, style_preset=style_preset,
        participation_mode=participation_mode,
    )
    await queries.create_agent(agent)
    locale = get_locale(request)
    strings = get_strings(locale)
    agents = await queries.list_agents()
    llm_configs = await queries.list_llm_configs()
    llm_map = {c.id: c for c in llm_configs}
    return templates.TemplateResponse(
        request,
        "fragments/agents.html",
        {"request": request, "locale": locale, "strings": strings,
         "agents": agents, "llm_configs": llm_configs, "llm_map": llm_map},
    )


@router.put("/fragments/agents/{agent_id}", response_class=HTMLResponse)
async def fragment_update_agent(
    request: Request,
    agent_id: int,
    name: str = Form(...),
    llm_config_id: int = Form(...),
    system_prompt: str = Form(""),
    style_preset: str = Form("custom"),
    participation_mode: str = Form(...),
):
    agent = await queries.get_agent(agent_id)
    if agent:
        agent.name = name
        agent.llm_config_id = llm_config_id
        agent.system_prompt = system_prompt
        agent.style_preset = style_preset
        agent.participation_mode = participation_mode
        await queries.update_agent(agent)
    locale = get_locale(request)
    strings = get_strings(locale)
    agents = await queries.list_agents()
    llm_configs = await queries.list_llm_configs()
    llm_map = {c.id: c for c in llm_configs}
    return templates.TemplateResponse(
        request,
        "fragments/agents.html",
        {"request": request, "locale": locale, "strings": strings,
         "agents": agents, "llm_configs": llm_configs, "llm_map": llm_map},
    )


@router.delete("/fragments/agents/{agent_id}")
async def fragment_delete_agent(agent_id: int):
    await queries.delete_agent(agent_id)
    return Response(status_code=200)
```

- [ ] **Step 4: Update settings.html to add Agents section**

Add after the LLM Configs div, before the Language section:

```html
    <h3>{{ strings.agents }}</h3>
    <div id="agents-container" hx-get="/fragments/agents" hx-trigger="load"></div>
```

- [ ] **Step 5: Write agent route tests**

Create `tests/test_agent_routes.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db import queries
from app.db.models import LLMConfig, ApiKey, Agent


@pytest.mark.asyncio
async def test_agents_page(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/fragments/agents")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_agent(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        key = await queries.create_api_key(ApiKey(provider="openai", key_encrypted="enc"))
        await queries.create_llm_config(LLMConfig(provider="openai", model="gpt-4o", api_key_id=key.id))
        resp = await client.post(
            "/fragments/agents",
            data={
                "name": "MyAgent",
                "llm_config_id": "1",
                "system_prompt": "Be helpful",
                "style_preset": "brief",
                "participation_mode": "always",
            },
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_agent_missing_name(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/fragments/agents", data={"llm_config_id": "1"})
        assert resp.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_delete_agent(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        key = await queries.create_api_key(ApiKey(provider="openai", key_encrypted="enc"))
        config = await queries.create_llm_config(LLMConfig(provider="openai", model="gpt-4o", api_key_id=key.id))
        agent = await queries.create_agent(Agent(name="test", llm_config_id=config.id))
        resp = await client.delete(f"/fragments/agents/{agent.id}")
        assert resp.status_code == 200
```

- [ ] **Step 6: Run agent route tests**

Run: `pytest tests/test_agent_routes.py -v`
Expected: 4 PASS

- [ ] **Step 7: Commit**

```bash
git add app/routes/fragments.py app/templates/fragments/agents.html app/templates/pages/settings.html app/i18n/en.py app/i18n/zh.py tests/test_agent_routes.py
git commit -m "feat: add Agent CRUD routes, agents.html template, Settings integration, i18n strings"
```

---

### Task 6: Chat UI and message handler updates

**Files:**
- Modify: `app/routes/fragments.py` (message handler)
- Modify: `app/templates/fragments/messages.html`
- Modify: `app/templates/fragments/llm-configs.html` (remove name field)

- [ ] **Step 1: Update `fragment_post_message` to use agents**

Replace the relevant section in `fragment_post_message`:

```python
    # Determine which agents will respond (instead of LLM configs)
    agents_list = await queries.list_agents()
    responding = [a for a in agents_list if should_respond(a, content)]

    # Build HTML: user message + placeholders for each responding agent
    html_parts = [f'<div class="message user" id="msg-{user_msg.id}">'
                  f'<div class="message-body"><div class="message-bubble">{escape(user_msg.content)}</div>'
                  f'</div></div>']

    for agent in responding:
        placeholder_id = f"placeholder-{agent.id}-{user_msg.id}"
        avatar_class = f"avatar-{agent.id % 8}"
        html_parts.append(
            f'<div class="message llm generating" id="{placeholder_id}">'
            f'<div class="message-avatar {avatar_class}">{agent.name[0]}</div>'
            f'<div class="message-body">'
            f'<div class="message-sender">{escape(agent.name)}</div>'
            f'<div class="message-bubble">generating...</div>'
            f'</div></div>'
        )
```

- [ ] **Step 2: Update SSE script — use agent_id instead of config.id for placeholders**

The SSE events still use `llm_config_id` in the payload (unchanged), but we need to map it to the correct placeholder. Since the SSE `token` and `complete` events carry `llm_config_id` from the orchestrator, and the orchestrator now receives agent, we need the Web UI to know which placeholder to update. There are two approaches:

**Approach chosen:** The SSE event carries `llm_config_id` (set by orchestrator). Before the event is sent, prepend an `agent_name` event that maps agent to llm_config_id for the client. OR: just add `agent_id` to the SSE events and use that for the placeholder.

Actually, simpler: The orchestrator already sends `llm_config_id` in events. The placeholder IDs use `agent.id`. We can send both IDs in the SSE events. Update `_run_llm_generation` to include `agent_id`:

In token events:
```python
await event_queue.put({
    "type": "token",
    "llm_config_id": config.id,
    "agent_id": agent.id,
    "token": token,
})
```

In complete events:
```python
await event_queue.put({
    "type": "complete",
    "llm_config_id": config.id,
    "agent_id": agent.id,
    "message_id": message.id,
    "content": full_content,
})
```

Then in the SSE connector script in `fragment_post_message`:
```javascript
es.addEventListener("token", function(e) {
    const data = JSON.parse(e.data);
    const el = document.getElementById("placeholder-" + data.agent_id + "-" + MSG_ID);
    if (el) {
        const bubble = el.querySelector(".message-bubble");
        if (bubble) {
            bubble.textContent += data.token;
            el.classList.remove("generating");
        }
    }
});
es.addEventListener("complete", function(e) {
    const data = JSON.parse(e.data);
    const el = document.getElementById("placeholder-" + data.agent_id + "-" + MSG_ID);
    if (el) {
        el.classList.remove("generating");
        const bubble = el.querySelector(".message-bubble");
        if (bubble && data.content) {
            bubble.innerHTML = DOMPurify.sanitize(marked.parse(data.content));
            bubble.classList.add("rendered");
        }
    }
});
es.addEventListener("llm-error", function(e) {
    const data = JSON.parse(e.data);
    const el = document.getElementById("placeholder-" + data.agent_id + "-" + MSG_ID);
    if (el) {
        el.classList.remove("generating");
        const bubble = el.querySelector(".message-bubble");
        if (bubble) bubble.textContent = "[Error] " + (data.error || "");
    }
});
```

- [ ] **Step 3: Update messages.html — agent list in header dropdown**

Replace the LLM config loop with an agent loop:

```html
{% for a in agents %}
<div style="padding: 6px 12px; font-size: 12px; display: flex; align-items: center; gap: 8px;">
    <span class="message-avatar avatar-{{ a.id % 8 }}" style="width: 20px; height: 20px; font-size: 10px;">
        {{ a.name[0] }}
    </span>
    <span style="color: var(--text-primary);">{{ a.name }}</span>
    <span style="color: var(--text-muted); font-size: 10px; margin-left: auto;">{{ a.style_preset }}</span>
</div>
{% endfor %}
```

Update the header LLM count to use agent count:
```html
{{ strings.llms_active.replace('{count}', agent_count|string) }} ▾
```

- [ ] **Step 4: Update messages.html — @mention autocomplete uses agent names**

```javascript
const LLM_NAMES = {{ agents | map(attribute='name') | list | tojson }};
LLM_NAMES.unshift("{{ 'Everyone' if locale == 'en' else '所有AI' }}");
```

- [ ] **Step 5: Update fragment_messages to pass agents**

In `fragment_messages` (fragments.py), add agents to the template context:

```python
    agents = await queries.list_agents()

    return templates.TemplateResponse(
        request,
        "fragments/messages.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversation": conversation, "messages": enriched,
         "llm_count": len(agents), "agents": agents},
    )
```

- [ ] **Step 6: Update llm-configs.html — remove name field from create form**

Remove the `name` input field from both the create form and the edit form. The LLM Config is now identified by `provider / model` combination.

- [ ] **Step 7: Commit**

```bash
git add app/routes/fragments.py app/templates/fragments/messages.html app/templates/fragments/llm-configs.html
git commit -m "feat: update chat UI and message handler to use Agents"
```

---

### Task 7: Integration — run full test suite and fix issues

**Files:**
- Modify: `app/routes/fragments.py` (update remaining references)
- Modify: `app/routes/settings.py` (update to pass agents to settings page)
- Modify: `app/routes/pages.py` (if needed)

- [ ] **Step 1: Update settings.py to pass agents to template**

```python
    agents = await queries.list_agents()
    return templates.TemplateResponse(
        request,
        "pages/settings.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversations": conversations, "api_keys": api_keys, "configs": configs, "agents": agents},
    )
```

- [ ] **Step 2: Update llm-configs.html edit form — remove name field**

In the edit form section of `llm-configs.html`, remove the `<input name="name" ...>` field. The form only needs `model`, `participation_mode` becomes n/a, `api_key_id` stays... actually wait — `participation_mode` was moved to Agent. So the LLM Config edit form should remove both `name` and `participation_mode`. The remaining fields are: model (display only), api_key_id, is_title_generator checkbox.

Let me check the current form... Looking at the template, the edit form has: name, model, participation_mode, api_key_id, is_title_generator. We need to remove name and participation_mode, keep model, api_key_id, is_title_generator.

- [ ] **Step 3: Update fragment_update_llm_config to remove name/participation_mode from form**

The PUT handler currently accepts `name` and `participation_mode`. Remove these params:

```python
@router.put("/fragments/llm-configs/{config_id}", response_class=HTMLResponse)
async def fragment_update_llm_config(
    request: Request,
    config_id: int,
    model: str = Form(...),
    api_key_id: int = Form(...),
    is_title_generator: str = Form("false"),
):
    is_title = is_title_generator in ("true", "on", "1")
    if is_title:
        all_configs = await queries.list_llm_configs()
        for c in all_configs:
            if c.id != config_id and c.is_title_generator:
                c.is_title_generator = False
                await queries.update_llm_config(c)

    config = await queries.get_llm_config(config_id)
    if config:
        config.model = model
        config.api_key_id = api_key_id
        config.is_title_generator = is_title
        await queries.update_llm_config(config)
    # ...
```

- [ ] **Step 4: Update llm-configs.html edit form to match**

Remove `name` and `participation_mode` inputs from the edit form, keep model, api_key_id, is_title_generator.

- [ ] **Step 5: Update fragment_create_llm_config**

```python
@router.post("/fragments/llm-configs", response_class=HTMLResponse)
async def fragment_create_llm_config(
    request: Request,
    provider: str = Form(...),
    model: str = Form(...),
    api_key_id: int = Form(...),
):
    config = LLMConfig(provider=provider, model=model, api_key_id=api_key_id)
    await queries.create_llm_config(config)
    # ...
```

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass (some may need minor fixes due to schema changes)

- [ ] **Step 7: Fix any failing tests**

Debug and fix any test that fails due to missing agents or schema mismatch.

- [ ] **Step 8: Final commit**

```bash
git add -A
git commit -m "feat: complete Agent layer integration — Settings, routes, templates, tests"
```
