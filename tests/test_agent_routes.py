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
