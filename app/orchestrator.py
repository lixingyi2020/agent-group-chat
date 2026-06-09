import asyncio
import logging
import random
import re
from typing import Optional, TypeVar, Callable, Awaitable
from app.db.models import Agent, Message
from app.db import queries
from app.providers import get_provider
from app.providers.base import LLMRequest, ProviderError
from app.crypto import decrypt

logger = logging.getLogger(__name__)

MENTION_RE = re.compile(r"@(\S+)")

MAX_CHAIN_DEPTH = 2
MAX_CONCURRENT = 5

# Debate: LLMs auto-debate each other's answers after user raises a topic
MIN_DEBATE_ROUNDS = 1
MAX_DEBATE_ROUNDS = 5
DEBATE_PROMPT = (
    "Critically analyze the previous responses above. "
    "If you disagree, explain why and offer evidence. "
    "If you agree, add new supporting points or perspectives. "
    "Avoid simply repeating what has already been said. "
    "Be concise and focused."
)

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


EVERYONE_ALIASES = {"Everyone", "everyone", "所有AI", "所有人", "all"}


def should_respond(agent: Agent, message_text: str, is_self: bool = False,
                   mention_names: list[str] | None = None) -> bool:
    if mention_names is None:
        mention_names = extract_mentions(message_text)

    # @Everyone triggers all agents regardless of participation mode
    everyone_mentioned = bool(EVERYONE_ALIASES & set(mention_names))
    if everyone_mentioned:
        return True

    # If specific agents are @mentioned, ONLY those respond — ignore participation modes
    specific_mentions = [n for n in mention_names if n not in EVERYONE_ALIASES]
    if specific_mentions:
        return agent.name in specific_mentions

    # No @mentions at all — use normal participation mode
    if is_self:
        return False

    if agent.participation_mode == "always":
        return True

    if agent.participation_mode == "probabilistic":
        return random.random() < agent.probability

    return False


# ── Generation task ─────────────────────────────────────────────────────────

async def _build_messages(conversation_id: int) -> list[dict]:
    db_messages = await queries.get_messages(conversation_id)
    # Map internal roles to OpenAI-compatible roles; skip empty messages
    role_map = {"user": "user", "llm": "assistant", "system": "system"}
    result = []
    for m in db_messages:
        if not m.content.strip():
            continue
        result.append({"role": role_map.get(m.role, m.role), "content": m.content})
    return result


async def _run_llm_generation(
    agent: Agent,
    conversation_id: int,
    event_queue: asyncio.Queue,
    depth: int = 0,
    debate_context: str = None,
) -> Optional[Message]:
    config = await queries.get_llm_config(agent.llm_config_id)
    if not config:
        await event_queue.put({
            "type": "llm-error",
            "llm_config_id": agent.llm_config_id,
            "agent_id": agent.id,
            "error": f"LLM config not found for agent {agent.name}",
            "retryable": False,
        })
        return None

    provider = get_provider(config.provider)
    request = None
    print(f"[LLM] {agent.name} ({config.provider}/{config.model}) starting...", flush=True)
    try:
        api_key_record = await queries.get_api_key(config.api_key_id)
        if not api_key_record:
            print(f"[LLM] {agent.name}: No API key found (id={config.api_key_id})", flush=True)
            raise ProviderError(f"No API key configured for {config.provider}", status_code=0, retryable=False)

        api_key = decrypt(api_key_record.key_encrypted)
        messages = await _build_messages(conversation_id)

        # Inject debate instruction as a user message so the LLM responds to it
        if debate_context:
            messages.append({"role": "user", "content": debate_context})

        # Reasoning models (DeepSeek) burn tokens on internal thought — give them headroom
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
                "agent_id": agent.id,
                "token": token,
            })
        print(f"[LLM] {agent.name}: stream complete, {len(full_content)} chars. Pushing to queue...", flush=True)

        if not full_content.strip():
            print(f"[LLM] {agent.name}: empty response, skipping save", flush=True)
            await event_queue.put({
                "type": "llm-error",
                "llm_config_id": config.id,
                "agent_id": agent.id,
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
            "agent_id": agent.id,
            "message_id": message.id,
            "content": full_content,
        })
        print(f"[LLM] {agent.name}: complete event pushed. DB message id={message.id}", flush=True)

        # Check for LLM-to-LLM mentions
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
        print(f"[LLM] {agent.name}: ProviderError: {e} (retryable={e.retryable})", flush=True)
        if e.retryable and request is not None:
            try:
                response = await with_retries(provider.generate, request)
                full_content = response.content
                await event_queue.put({"type": "token", "llm_config_id": config.id, "agent_id": agent.id, "token": full_content})
                message = await queries.create_message(
                    conversation_id, "llm", full_content, config.id, agent_id=agent.id
                )
                await event_queue.put({
                    "type": "complete",
                    "llm_config_id": config.id,
                    "agent_id": agent.id,
                    "message_id": message.id,
                    "content": full_content,
                })
                return message
            except Exception as retry_err:
                logger.warning(f"Retry failed for {agent.name}: {retry_err}")
        await event_queue.put({
            "type": "llm-error",
            "llm_config_id": config.id,
            "agent_id": agent.id,
            "error": str(e),
            "retryable": e.retryable,
        })
        return None
    except Exception as e:
        logger.exception(f"Unexpected error for LLM {agent.name}: {e}")
        await event_queue.put({
            "type": "llm-error",
            "llm_config_id": config.id,
            "agent_id": agent.id,
            "error": str(e),
            "retryable": False,
        })
        return None


# ── Orchestration ───────────────────────────────────────────────────────────

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

    # ── Debate rounds ──────────────────────────────────────────────────────
    if depth == 0:
        for round_num in range(1, MAX_DEBATE_ROUNDS + 1):
            agents = await queries.list_agents()

            # Select debate participants: always + probabilistic agents
            debaters = []
            for agent in agents:
                if agent.participation_mode == "always":
                    debaters.append(agent)
                elif agent.participation_mode == "probabilistic" and random.random() < agent.probability:
                    debaters.append(agent)

            if len(debaters) < 2:
                break

            debate_context = f"[Debate Round {round_num}] {DEBATE_PROMPT}"
            print(f"[Orchestrator] Debate round {round_num}: {[a.name for a in debaters]}", flush=True)

            async def _run_debate(agent: Agent):
                async with semaphore:
                    return await _run_llm_generation(
                        agent, conversation_id, event_queue, depth, debate_context
                    )

            results = await asyncio.gather(*[_run_debate(a) for a in debaters])
            responded = [r for r in results if r is not None]
            print(f"[Orchestrator] Debate round {round_num}: {len(responded)} responded", flush=True)

            if len(responded) < 2 and round_num >= MIN_DEBATE_ROUNDS:
                break
