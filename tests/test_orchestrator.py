import pytest
from unittest.mock import patch
from app.db.models import Agent, LLMConfig, ApiKey
from app.db import queries
from app.orchestrator import orchestrate_llm_responses
from app.routes.stream import get_or_create_queue, remove_queue


@pytest.mark.asyncio
async def test_orchestrate_with_mention_only_config(db):
    conv = await queries.create_conversation("test")
    await queries.create_message(conv.id, "user", "Hello @claude")

    key = await queries.create_api_key(ApiKey(provider="openai", key_encrypted="encrypted"))
    config = LLMConfig(provider="openai", model="gpt-4o", api_key_id=key.id)
    config = await queries.create_llm_config(config)
    agent = Agent(name="claude", llm_config_id=config.id, participation_mode="mention_only")
    await queries.create_agent(agent)

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
    config = LLMConfig(provider="openai", model="gpt-4o", api_key_id=key.id)
    config = await queries.create_llm_config(config)
    agent = Agent(name="claude", llm_config_id=config.id, participation_mode="mention_only")
    await queries.create_agent(agent)

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
    config = LLMConfig(provider="openai", model="gpt-4o", api_key_id=key.id)
    config = await queries.create_llm_config(config)
    agent = Agent(name="claude", llm_config_id=config.id, participation_mode="always")
    await queries.create_agent(agent)

    queue = get_or_create_queue(conv.id)

    with patch("app.orchestrator._run_llm_generation") as mock_run:
        mock_run.return_value = None
        await orchestrate_llm_responses(conv.id, queue, "Any message")
        mock_run.assert_called_once()

    remove_queue(conv.id)
