import asyncio
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, Response
from app.db import queries
from app.db.models import LLMConfig
from app.i18n import get_locale, get_strings
from app.templates import templates
from app.orchestrator import orchestrate_llm_responses, should_respond, extract_mentions
from app.routes.stream import get_or_create_queue

router = APIRouter()


@router.get("/fragments/conversations", response_class=HTMLResponse)
async def fragment_conversations(request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    conversations = await queries.list_conversations()
    return templates.TemplateResponse(
        request,
        "fragments/conversations.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversations": conversations},
    )


@router.post("/fragments/conversations", response_class=HTMLResponse)
async def fragment_create_conversation(request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    conv = await queries.create_conversation()
    conversations = await queries.list_conversations()
    response = templates.TemplateResponse(
        request,
        "fragments/conversations.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversations": conversations, "active_id": conv.id},
    )
    response.headers["HX-Redirect"] = f"/conversations/{conv.id}"
    return response


@router.get("/fragments/conversations/{conversation_id}/messages", response_class=HTMLResponse)
async def fragment_messages(conversation_id: int, request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    conversation = await queries.get_conversation(conversation_id)
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
        request,
        "fragments/messages.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversation": conversation, "messages": enriched,
         "llm_count": len(configs)},
    )


@router.post("/fragments/conversations/{conversation_id}/messages", response_class=HTMLResponse)
async def fragment_post_message(conversation_id: int, content: str = Form(...)):
    configs = await queries.list_llm_configs()

    # Save user message
    user_msg = await queries.create_message(conversation_id, "user", content)

    # Determine which LLMs will respond
    responding = [c for c in configs if should_respond(c, content)]

    # Build HTML: user message + placeholders for each responding LLM
    html_parts = [f'<div class="message user" id="msg-{user_msg.id}">'
                  f'<div class="message-body"><div class="message-bubble">{user_msg.content}</div>'
                  f'</div></div>']

    avatar_colors = [f"avatar-{i}" for i in range(8)]
    for config in responding:
        avatar_class = avatar_colors[config.id % 8]
        html_parts.append(
            f'<div class="message llm generating" id="placeholder-{config.id}">'
            f'<div class="message-avatar {avatar_class}">{config.name[0]}</div>'
            f'<div class="message-body">'
            f'<div class="message-sender">{config.name}</div>'
            f'<div class="message-bubble">generating...</div>'
            f'</div></div>'
        )

    response = Response(content="\n".join(html_parts), media_type="text/html")
    response.headers["HX-Trigger"] = "sseConnect"

    # Kick off async orchestration
    queue = get_or_create_queue(conversation_id)
    asyncio.create_task(orchestrate_llm_responses(conversation_id, queue, content))

    return response


@router.get("/fragments/llm-configs", response_class=HTMLResponse)
async def fragment_llm_configs(request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    configs = await queries.list_llm_configs()
    api_keys = await queries.list_api_keys()
    return templates.TemplateResponse(
        request,
        "fragments/llm-configs.html",
        {"request": request, "locale": locale, "strings": strings, "configs": configs, "api_keys": api_keys},
    )


@router.post("/fragments/llm-configs", response_class=HTMLResponse)
async def fragment_create_llm_config(
    request: Request,
    name: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    participation_mode: str = Form("mention_only"),
    api_key_id: int = Form(...),
):
    config = LLMConfig(
        name=name, provider=provider, model=model,
        participation_mode=participation_mode, api_key_id=api_key_id,
    )
    await queries.create_llm_config(config)
    locale = get_locale(request)
    strings = get_strings(locale)
    configs = await queries.list_llm_configs()
    api_keys = await queries.list_api_keys()
    return templates.TemplateResponse(
        request,
        "fragments/llm-configs.html",
        {"request": request, "locale": locale, "strings": strings, "configs": configs, "api_keys": api_keys},
    )


@router.delete("/fragments/llm-configs/{config_id}", response_class=HTMLResponse)
async def fragment_delete_llm_config(config_id: int):
    await queries.delete_llm_config(config_id)
    return Response(status_code=200)


@router.post("/fragments/settings/language")
async def fragment_set_language(lang: str = Form(...)):
    response = Response(status_code=200)
    response.set_cookie("lang", lang)
    response.headers["HX-Refresh"] = "true"
    return response
