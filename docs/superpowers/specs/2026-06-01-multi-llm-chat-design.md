# Multi-LLM Group Chat — Design Spec

**Date:** 2026-06-01
**Status:** Approved

## Overview

A web-based chat application where a user converses with multiple AI LLMs in a single group-chat conversation. LLMs can talk to each other — they can @mention one another, respond autonomously based on configurable participation modes, and build on each other's responses.

## Core Decisions

| Area | Decision |
|------|----------|
| Interaction model | Group chat — user + LLMs as equal participants |
| LLM participation | Configurable per LLM: @mention, always-on, probabilistic |
| LLM connectivity | User brings own API keys (BYO) |
| Deployment model | SPA + thin backend proxy (avoids CORS) |
| Tech stack | Python FastAPI + HTMX + SQLite |
| Message delivery | Hybrid: SSE streaming for direct interactions, full-message for auto-responses |
| LLM context | Full conversation history per LLM |
| Persistence | Conversations persist across sessions |
| Users | Single-user, no auth |
| Response length | 400 characters default, configurable per LLM |
| Language | Simplified Chinese default, English optional, switchable in sidebar + settings |

## System Architecture

Single FastAPI process using asyncio. No Redis, no background workers. LLM calls are I/O-bound, so `asyncio.gather` handles concurrency.

```
Browser (HTMX + SSE) ──HTTP──▶ FastAPI ──SQL──▶ SQLite
                                   │
                                   └──HTTPS──▶ OpenAI / Anthropic / Google / ...
```

### Project Structure

```
agent-chat/
├── app/
│   ├── main.py              # FastAPI app, lifespan, route registration
│   ├── routes/
│   │   ├── pages.py         # Full page routes (GET /)
│   │   ├── fragments.py     # HTMX fragment routes
│   │   ├── stream.py        # SSE endpoint
│   │   └── settings.py      # Settings/API key management
│   ├── orchestrator.py      # Multi-LLM coordination logic
│   ├── providers/
│   │   ├── base.py          # Abstract adapter interface
│   │   ├── openai.py
│   │   ├── anthropic.py
│   │   └── google.py
│   ├── db/
│   │   ├── models.py        # SQLAlchemy or dataclass models
│   │   ├── queries.py       # Database operations
│   │   └── migrations.py    # Schema setup/migration
│   ├── templates/
│   │   ├── base.html        # Shell layout
│   │   ├── fragments/       # HTMX partials
│   │   └── pages/           # Full page templates
│   ├── i18n/
│   │   ├── zh.py            # Simplified Chinese strings
│   │   └── en.py            # English strings
│   └── crypto.py            # Fernet key encryption
├── tests/
│   ├── test_participation.py
│   ├── test_orchestrator.py
│   ├── test_providers.py
│   ├── test_routes.py
│   └── test_db.py
├── static/                   # Minimal CSS/JS
├── requirements.txt
└── README.md
```

## Data Model

### conversations
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| title | TEXT | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### messages
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| conversation_id | INTEGER FK | |
| role | TEXT | "user", "llm", "system" |
| llm_config_id | INTEGER FK nullable | NULL for user messages |
| content | TEXT | |
| created_at | TIMESTAMP | |

### llm_configs
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | TEXT | Display name in chat |
| provider | TEXT | "openai", "anthropic", "google", "openai_compatible" |
| model | TEXT | e.g. "gpt-4o", "claude-sonnet-4-6" |
| api_key_id | INTEGER FK | |
| participation_mode | TEXT | "mention_only", "always", "probabilistic" |
| probability | REAL | 0.0–1.0, used when mode = "probabilistic" |
| max_response_chars | INTEGER | Default 400 |
| system_prompt | TEXT | Optional, customizes LLM personality |
| created_at | TIMESTAMP | |

### api_keys
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| provider | TEXT | |
| key_encrypted | TEXT | Fernet-encrypted |
| created_at | TIMESTAMP | |

### settings
| Column | Type | Notes |
|--------|------|-------|
| key | TEXT PK | e.g. "language", "theme" |
| value | TEXT | |

## API Routes

### Pages (full HTML)
| Route | Returns |
|-------|---------|
| `GET /` | Main app shell |
| `GET /conversations/{id}` | Full conversation page |

### HTMX Fragments (HTML partials)
| Route | Purpose |
|-------|---------|
| `GET /fragments/conversations` | Conversation sidebar list |
| `GET /fragments/conversations/{id}/messages` | Message history |
| `POST /fragments/conversations/{id}/messages` | Submit user message → triggers orchestration |
| `GET /fragments/conversations/new` | New conversation form |
| `POST /fragments/conversations` | Create conversation |
| `GET /fragments/llm-configs` | LLM config management panel |
| `POST /fragments/llm-configs` | Create/edit LLM config |
| `DELETE /fragments/llm-configs/{id}` | Remove LLM config |

### SSE Streaming
| Route | Purpose |
|-------|---------|
| `GET /stream/conversations/{id}` | Single SSE connection for all active LLM streams in a conversation |

### Settings
| Route | Purpose |
|-------|---------|
| `GET /settings` | Settings page |
| `POST /settings/keys` | Add/update API key |
| `DELETE /settings/keys/{id}` | Remove API key |

## Multi-LLM Orchestration

### Participation Trigger Logic

When a user or LLM sends a message:

1. **Parse @mentions** — extract mentioned LLM names from message text
2. **For each configured LLM**, determine if it should respond:
   - `@mentioned` → always respond (bypasses all other rules)
   - `participation_mode = "always"` → respond to every message
   - `participation_mode = "probabilistic"` → roll `random() < probability`
   - `participation_mode = "mention_only"` → skip unless @mentioned
3. **Launch concurrent async tasks** for each responding LLM
4. **Chain detection**: if an LLM @mentions another LLM, step 2 runs again for the new message (depth-limited)

### Safeguards

- **Depth limit**: LLM-to-LLM chains capped at 2 hops
- **Self-reply prevention**: an LLM won't respond to its own message (even in "always" mode) unless @mentioned
- **Concurrency cap**: max 5 simultaneous LLM API calls; excess queue
- **Timeout**: 60s per LLM call

## SSE Streaming Flow

One SSE connection per conversation. Events are tagged with `llm_config_id` so the frontend routes tokens to the correct placeholder.

```
POST /fragments/conversations/{id}/messages
  → Returns HTML: user message + placeholders
  → HX-Trigger: connect SSE

GET /stream/conversations/{id}
  → event: chunk  {"llm_config_id": 3, "token": "..."}
  → event: done   {"llm_config_id": 3, "message_id": 42}
  → event: error  {"llm_config_id": 2, "error": "timeout"}
```

All LLM tasks push to a shared `asyncio.Queue`. The SSE endpoint reads from it and yields Server-Sent Events.

## Error Handling

| Failure | Handling |
|---------|----------|
| Timeout (60s) | Placeholder → "timed out" + retry link |
| Rate limit (429) | Exponential backoff, up to 3 retries |
| Invalid key (401) | Immediate error, link to settings |
| Server error (5xx) | One retry, then error + retry link |
| SSE disconnect | Tasks continue, missed messages loaded from DB on reconnect |
| DB write failure | Log, warn, conversation readable in-memory |
| Token limit exceeded | Trim oldest messages (preserving @mentions) |

**Fault isolation**: one LLM's failure never blocks another. Errors are scoped to individual participants.

## i18n

- **Default**: Simplified Chinese (zh-CN)
- **Switchable to**: English (en-US)
- **Locations**: sidebar dropdown (always visible) + Settings page
- **Scope**: UI chrome only — labels, buttons, placeholders, status/error messages. LLM responses and user messages are never translated.
- **Implementation**: Jinja2 templates with translation keys, language stored in `settings` table + cookie

## UI Layout

Two-panel layout (Slack-style):

- **Left sidebar**: conversation list, "+ New Chat" button, language switcher dropdown at bottom
- **Right chat area**: header (title + active LLM count), scrollable message list, input bar with @mention support
- **Messages**: user messages right-aligned blue bubbles; each LLM has a color-coded avatar + name badge, left-aligned bubbles
- **Streaming**: "generating..." placeholder replaced token-by-token via SSE
- **Settings**: gear icon → settings page for API keys, LLM configs, language

## Testing Strategy

| Type | Scope | Tooling |
|------|-------|---------|
| Unit | Provider adapters (mocked), participation logic, token counting, prompt building | pytest + pytest-asyncio |
| Integration | DB operations, SSE queue, full message flow (mocked LLMs), route HTML output | pytest + httpx |
| Manual | Real LLM calls, streaming UX, @mention autocomplete | Browser |

### Key Test Scenarios
- Participation logic: all modes, @mention override, boundary probabilities
- Orchestrator: concurrent tasks, fault isolation, depth limit, self-reply prevention
- SSE fan-in: multi-stream token routing, done/error events
- Context window: trimming preserves @mentions, token counting accuracy
- Database: CRUD, cascade delete, key encryption round-trip
