from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.db import queries
from app.i18n import get_locale, get_strings
from app.templates import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    conversations = await queries.list_conversations()
    return templates.TemplateResponse(
        "pages/index.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversations": conversations, "conversation": None,
         "llm_count": 0},
    )


@router.get("/conversations/{conversation_id}", response_class=HTMLResponse)
async def conversation_page(conversation_id: int, request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    conversations = await queries.list_conversations()
    conversation = await queries.get_conversation(conversation_id)
    if not conversation:
        return templates.TemplateResponse(
            "pages/index.html",
            {"request": request, "locale": locale, "strings": strings,
             "conversations": conversations, "conversation": None,
             "llm_count": 0},
            status_code=404,
        )
    messages = await queries.get_messages(conversation_id)
    configs = await queries.list_llm_configs()

    config_map = {c.id: c.name for c in configs}
    enriched = []
    for msg in messages:
        enriched.append({
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "role": msg.role,
            "llm_config_id": msg.llm_config_id,
            "content": msg.content,
            "created_at": msg.created_at,
            "llm_name": config_map.get(msg.llm_config_id, "") if msg.llm_config_id else "",
        })

    return templates.TemplateResponse(
        "pages/index.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversations": conversations, "conversation": conversation,
         "messages": enriched, "llm_count": len(configs),
         "active_id": conversation_id},
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    conversations = await queries.list_conversations()
    api_keys = await queries.list_api_keys()
    configs = await queries.list_llm_configs()
    return templates.TemplateResponse(
        "pages/settings.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversations": conversations, "api_keys": api_keys,
         "configs": configs},
    )
