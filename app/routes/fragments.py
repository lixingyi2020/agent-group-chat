import asyncio
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, Response
from app.db import queries
from app.db.models import LLMConfig, ApiKey
from app.i18n import get_locale, get_strings
from app.templates import templates
from app.orchestrator import orchestrate_llm_responses, should_respond, extract_mentions
from app.routes.stream import get_or_create_queue

router = APIRouter()


async def _auto_title(conversation_id: int, first_message: str, config):
    """Generate a short title for the conversation using the first available LLM."""
    try:
        from app.crypto import decrypt
        from app.providers import get_provider
        from app.providers.base import LLMRequest

        print(f"[AutoTitle] Starting for conv {conversation_id} with {config.name} (key_id={config.api_key_id})", flush=True)

        key_record = await queries.get_api_key(config.api_key_id)
        if not key_record:
            print(f"[AutoTitle] No API key found for key_id={config.api_key_id}", flush=True)
            return
        api_key = decrypt(key_record.key_encrypted)
        print(f"[AutoTitle] Key decrypted, calling {config.provider}/{config.model}...", flush=True)

        provider = get_provider(config.provider)

        request = LLMRequest(
            model=config.model,
            api_key=api_key,
            system_prompt="Generate a SHORT title (max 6 words) summarizing the user's message. Reply with ONLY the title, no quotes.",
            messages=[{"role": "user", "content": first_message}],
            max_tokens=30,
        )
        response = await provider.generate(request)
        title = response.content.strip().strip('"').strip("'")[:50]
        print(f"[AutoTitle] Response: '{response.content}' -> title: '{title}'", flush=True)
        if title:
            await queries.update_conversation_title(conversation_id, title)
            print(f"[AutoTitle] Title saved: {title}", flush=True)
    except Exception as e:
        print(f"[AutoTitle] Failed: {type(e).__name__}: {e}", flush=True)


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
         "llm_count": len(configs), "llm_configs": configs},
    )


@router.post("/fragments/conversations/{conversation_id}/messages", response_class=HTMLResponse)
async def fragment_post_message(conversation_id: int, content: str = Form(...)):
    configs = await queries.list_llm_configs()

    # Save user message
    user_msg = await queries.create_message(conversation_id, "user", content)

    # #1: Auto-title generation — if this is the first user message, generate a title
    all_msgs = await queries.get_messages(conversation_id)
    user_count = sum(1 for m in all_msgs if m.role == "user")
    if user_count == 1 and configs:
        print(f"[AutoTitle] Triggering for conversation {conversation_id} with LLM {configs[0].name}", flush=True)
        asyncio.create_task(_auto_title(conversation_id, content, configs[0]))

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

    # Embed SSE connector script directly in the response
    html_parts.append(f'''<script>
        (function() {{
            const es = new EventSource("/stream/conversations/{conversation_id}");
            es.addEventListener("token", function(e) {{
                const data = JSON.parse(e.data);
                const el = document.getElementById("placeholder-" + data.llm_config_id);
                if (el) {{
                    const bubble = el.querySelector(".message-bubble");
                    if (bubble) {{
                        bubble.textContent += data.token;
                        el.classList.remove("generating");
                    }}
                }}
            }});
            es.addEventListener("complete", function(e) {{
                const data = JSON.parse(e.data);
                const el = document.getElementById("placeholder-" + data.llm_config_id);
                if (el) {{
                    el.classList.remove("generating");
                    const bubble = el.querySelector(".message-bubble");
                    if (bubble && data.content) bubble.textContent = data.content;
                }}
            }});
            es.addEventListener("llm-error", function(e) {{
                const data = JSON.parse(e.data);
                const el = document.getElementById("placeholder-" + data.llm_config_id);
                if (el) {{
                    el.classList.remove("generating");
                    const bubble = el.querySelector(".message-bubble");
                    if (bubble) bubble.textContent = "[Error] " + (data.error || "");
                }}
            }});
        }})();
    </script>''')

    # Kick off async orchestration
    queue = get_or_create_queue(conversation_id)
    asyncio.create_task(orchestrate_llm_responses(conversation_id, queue, content))

    return Response(content="\n".join(html_parts), media_type="text/html")


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


@router.post("/fragments/quick-add-key", response_class=HTMLResponse)
async def fragment_quick_add_key(request: Request, provider: str = Form(...), key: str = Form(...)):
    from app.crypto import encrypt
    encrypted = encrypt(key)
    await queries.create_api_key(ApiKey(provider=provider, key_encrypted=encrypted))
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
