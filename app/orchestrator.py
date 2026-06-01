import asyncio
import logging
import random
import re
from typing import Optional, TypeVar, Callable, Awaitable
from app.db.models import LLMConfig, Message
from app.db import queries
from app.providers import get_provider
from app.providers.base import LLMRequest, ProviderError
from app.crypto import decrypt

logger = logging.getLogger(__name__)

MENTION_RE = re.compile(r"@(\S+)")

MAX_CHAIN_DEPTH = 2
MAX_CONCURRENT = 5

T = TypeVar("T")


# ── Retry wrapper ──────────────────────────────────────────────────────────

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


# ── Participation logic ─────────────────────────────────────────────────────

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


# ── Generation task ─────────────────────────────────────────────────────────

async def _build_messages(conversation_id: int) -> list[dict]:
    db_messages = await queries.get_messages(conversation_id)
    # Map internal roles to OpenAI-compatible roles
    role_map = {"user": "user", "llm": "assistant", "system": "system"}
    return [{"role": role_map.get(m.role, m.role), "content": m.content} for m in db_messages]


async def _run_llm_generation(
    config: LLMConfig,
    conversation_id: int,
    event_queue: asyncio.Queue,
    depth: int = 0,
) -> Optional[Message]:
    provider = get_provider(config.provider)
    request = None
    print(f"[LLM] {config.name} ({config.provider}/{config.model}) starting...", flush=True)
    try:
        api_key_record = await queries.get_api_key(config.api_key_id)
        if not api_key_record:
            print(f"[LLM] {config.name}: No API key found (id={config.api_key_id})", flush=True)
            raise ProviderError(f"No API key configured for {config.provider}", status_code=0, retryable=False)

        api_key = decrypt(api_key_record.key_encrypted)
        messages = await _build_messages(conversation_id)

        # Reasoning models (DeepSeek) burn tokens on internal thought — give them headroom
        if config.provider == "deepseek":
            max_tokens = max(config.max_response_chars * 4, 2000)
        else:
            max_tokens = config.max_response_chars

        request = LLMRequest(
            model=config.model,
            api_key=api_key,
            system_prompt=config.system_prompt,
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

        message = await queries.create_message(
            conversation_id, "llm", full_content, config.id
        )

        await event_queue.put({
            "type": "complete",
            "llm_config_id": config.id,
            "message_id": message.id,
            "content": full_content,
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
        print(f"[LLM] {config.name}: ProviderError: {e} (retryable={e.retryable})", flush=True)
        if e.retryable and request is not None:
            try:
                response = await with_retries(provider.generate, request)
                full_content = response.content
                await event_queue.put({"type": "token", "llm_config_id": config.id, "token": full_content})
                message = await queries.create_message(conversation_id, "llm", full_content, config.id)
                await event_queue.put({"type": "complete", "llm_config_id": config.id, "message_id": message.id, "content": full_content})
                return message
            except Exception as retry_err:
                logger.warning(f"Retry failed for {config.name}: {retry_err}")
        await event_queue.put({
            "type": "llm-error",
            "llm_config_id": config.id,
            "error": str(e),
            "retryable": e.retryable,
        })
        return None
    except Exception as e:
        logger.exception(f"Unexpected error for LLM {config.name}: {e}")
        await event_queue.put({
            "type": "llm-error",
            "llm_config_id": config.id,
            "error": str(e),
            "retryable": False,
        })
        return None


# ── Orchestration ───────────────────────────────────────────────────────────

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

    print(f"[Orchestrator] Triggering {len(tasks_to_run)} LLMs: {[c.name for c in tasks_to_run]}", flush=True)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def _run_with_limit(config: LLMConfig):
        async with semaphore:
            await _run_llm_generation(config, conversation_id, event_queue, depth)

    await asyncio.gather(*[_run_with_limit(c) for c in tasks_to_run])
