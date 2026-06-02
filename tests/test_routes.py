import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_index_returns_html(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_create_conversation(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/fragments/conversations")
        assert resp.status_code == 200
        assert "HX-Redirect" in resp.headers


@pytest.mark.asyncio
async def test_conversation_page(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/fragments/conversations")
        resp = await client.get("/conversations/1")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_post_message(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/fragments/conversations")
        resp = await client.post(
            "/fragments/conversations/1/messages",
            data={"content": "Hello world"},
        )
        assert resp.status_code == 200
        assert "Hello world" in resp.text


@pytest.mark.asyncio
async def test_settings_page(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/settings")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_add_api_key(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/settings/keys",
            data={"provider": "openai", "key": "sk-test123"},
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_add_llm_config(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/settings/keys", data={"provider": "openai", "key": "sk-test123"})
        resp = await client.post(
            "/fragments/llm-configs",
            data={
                "provider": "openai",
                "model": "gpt-4o",
                "api_key_id": "1",
            },
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_language_switch(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/fragments/settings/language", data={"lang": "en"})
        assert resp.status_code == 200
        assert "lang=en" in resp.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_i18n_defaults_to_chinese(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "群聊" in resp.text or "发送" in resp.text
