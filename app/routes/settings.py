from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response
from app.db import queries
from app.db.models import ApiKey
from app.crypto import encrypt
from app.i18n import get_locale, get_strings
from app.templates import templates

router = APIRouter()


@router.post("/settings/keys", response_class=HTMLResponse)
async def create_key(request: Request, provider: str = Form(...), key: str = Form(...)):
    encrypted = encrypt(key)
    await queries.create_api_key(ApiKey(provider=provider, key_encrypted=encrypted))

    locale = get_locale(request)
    strings = get_strings(locale)
    conversations = await queries.list_conversations()
    api_keys = await queries.list_api_keys()
    configs = await queries.list_llm_configs()
    return templates.TemplateResponse(
        "pages/settings.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversations": conversations, "api_keys": api_keys, "configs": configs},
    )


@router.delete("/settings/keys/{key_id}")
async def delete_key(key_id: int):
    await queries.delete_api_key(key_id)
    return Response(status_code=200)
