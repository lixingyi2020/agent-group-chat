# AI Agent Layer — Design Spec

> **Status:** Approved | **Date:** 2026-06-02

**Goal:** Introduce an Agent abstraction layer between LLM Configs (technical backend) and the group chat (user-facing participants), so that one LLM can power multiple agents with distinct names, personalities, and language styles.

**Context:** Currently `llm_configs` serves double duty — it holds both technical connection details (provider, model, API key) and participant identity (name, system_prompt, participation_mode). This prevents creating multiple chat personalities on the same LLM (e.g., a "serious assistant" and a "witty friend" both backed by GPT-4o).

---

## Architecture

```
LLM Config (technical layer)       Agent (participant layer)       Group Chat
┌──────────────────────────┐      ┌──────────────────────┐      ┌──────────┐
│ provider: openai          │──1:N─│ name: "小助手"        │──────│ @小助手   │
│ model: gpt-4o             │      │ style: rigorous       │      │ @老司机   │
│ api_key_id: 1             │      │ system_prompt: "..."  │      └──────────┘
│ max_response_chars: 200   │      │ participation_mode    │
│ is_title_generator: bool  │      └──────────────────────┘
└──────────────────────────┘
```

- **LLM Config** = pure technical backend: provider, model, API key, max_response_chars, is_title_generator
- **Agent** = chat participant: name, personality system_prompt, style preset, participation_mode, probability
- Multiple agents can share one LLM Config
- Agents participate in chat; LLM Configs no longer appear in @mentions or the chat header dropdown

---

## Data Model

### New table: `agents`

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

**Style presets** (editable): `brief` (简短), `rigorous` (严谨), `witty` (风趣), `custom` (自定义). Each has a default prompt snippet that the user can modify.

**System prompt priority:** Agent's `system_prompt` replaces LLM Config's `system_prompt` entirely. LLM Configs no longer have a `system_prompt` field.

### Modified table: `messages`

Add nullable `agent_id` column:

```sql
ALTER TABLE messages ADD COLUMN agent_id INTEGER REFERENCES agents(id) ON DELETE SET NULL;
```

Existing messages retain `llm_config_id` for backwards compatibility. New messages set both `agent_id` and `llm_config_id`.

### Modified table: `llm_configs`

Remove columns moved to agents:
- `name` — now on agent
- `system_prompt` — now on agent
- `participation_mode` — now on agent
- `probability` — now on agent

Retain:
- `provider`, `model`, `api_key_id` — technical connection
- `max_response_chars` — output limit stays at LLM level
- `is_title_generator` — stays at LLM level; when generating titles, use any agent of that LLM

### Auto-migration

On startup, if `agents` table does not exist:
1. Create `agents` table
2. For each existing `llm_config`, create a same-named agent copying `name`, `system_prompt`, `participation_mode`, `probability`
3. Add `agent_id` column to `messages` (nullable)

---

## API / Route Changes

### Agent CRUD (in fragments.py)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/fragments/agents` | Render agent list (for Settings page) |
| POST | `/fragments/agents` | Create new agent |
| PUT | `/fragments/agents/{id}` | Update agent (name, system_prompt, style, participation, llm_config_id) |
| DELETE | `/fragments/agents/{id}` | Delete agent |

### Query changes

| Function | Change |
|----------|--------|
| `list_agents()` | New: SELECT * FROM agents |
| `create_agent(agent)` | New |
| `update_agent(agent)` | New |
| `delete_agent(id)` | New |
| `get_agent(id)` | New |
| `get_agents_by_llm_config(llm_config_id)` | New: find all agents for an LLM |
| `list_llm_configs()` | Drop name/system_prompt/participation_mode/probability from SELECT |
| `create_message()` | Accept optional `agent_id` |
| `_row_to_message()` | Handle `agent_id` column |
| `_row_to_llm_config()` | Drop name/system_prompt/participation_mode/probability |

### Orchestrator changes

| Function | Change |
|----------|--------|
| `should_respond()` | Operate on Agent instead of LLMConfig; match against `agent.name` |
| `_run_llm_generation()` | Accept Agent param; resolve LLM Config from `agent.llm_config_id`; use `agent.system_prompt` |
| `orchestrate_llm_responses()` | List agents instead of configs; map agents → configs for LLM calls |
| `extract_mentions()` | No change |
| `_auto_title()` | Find agents of the title-generator LLM; use first agent's name |

### Settings page

Add third section after LLM Configs: "AI Agents / 智能助手". Rendered via HTMX fragment `/fragments/agents`.

Each agent card shows:
- Agent name, bound LLM name, style tag, participation mode
- Edit button → inline edit form with: name, llm_config dropdown, style preset selector + system_prompt textarea
- Delete button

### Chat UI

- `llm-count-dropdown` shows agents instead of LLM configs
- `@mention` autocomplete uses agent names
- LLM count in header = agent count
- Message sender name = agent name (from `agent_id` join)

---

## Style Presets

Default prompt snippets (editable by user):

| Preset | Label | Prompt Snippet |
|--------|-------|---------------|
| `brief` | 简短 | Reply concisely. Keep responses under 2-3 sentences. Get straight to the point. |
| `rigorous` | 严谨 | Reply with rigorous reasoning. Consider edge cases. Be precise and accurate. |
| `witty` | 风趣 | Reply with humor and wit. Use playful language and occasional jokes. |
| `custom` | 自定义 | (user-provided) |

When user selects a preset, the textarea is pre-filled. User can then edit freely.

---

## Testing Strategy

- **Unit tests:** `test_agent_queries.py` — CRUD operations for agents table
- **Integration tests:** `test_agent_routes.py` — agent CRUD endpoints
- **Orchestrator tests:** Update `test_participation.py` — should_respond now takes Agent
- **Migration tests:** Verify auto-migration creates correct agents from existing LLM configs

---

## Rollback Safety

- `messages.agent_id` is nullable — old messages work without it
- `messages.llm_config_id` is retained — no data loss
- `llm_configs` removed columns are safe: `name`/`system_prompt`/`participation_mode`/`probability` were already migrated to agents
- Rollback requires restoring from backup (standard SQLite migration risk)

---

## Files Changed

| File | Change |
|------|--------|
| `app/db/models.py` | Add `Agent` dataclass; remove fields from `LLMConfig`; add `agent_id` to `Message` |
| `app/db/migrations.py` | Create `agents` table; auto-migration logic; ALTER messages |
| `app/db/queries.py` | Agent CRUD; update `_row_to_llm_config`, `_row_to_message`, `create_message` |
| `app/orchestrator.py` | Operate on Agent; resolve LLM Config from agent |
| `app/routes/fragments.py` | Agent CRUD endpoints; update message handler to use agents |
| `app/templates/pages/settings.html` | Add agents section with HTMX lazy load |
| `app/templates/fragments/agents.html` | New: agent list/edit/create UI |
| `app/templates/fragments/messages.html` | Show agents in dropdown and @mention list |
| `app/templates/fragments/llm-configs.html` | Remove name field from create form |
| `tests/` | New test files; update existing orchestrator tests |
