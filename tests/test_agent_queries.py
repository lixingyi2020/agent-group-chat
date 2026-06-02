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
    conv = await queries.create_conversation("test")
    msg = await queries.create_message(conv.id, "llm", "Hello", agent_id=5)
    assert msg.agent_id == 5
