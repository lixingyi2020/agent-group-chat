import asyncio
from html import escape
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, Response
from app.db import queries
from app.db.models import LLMConfig, ApiKey, Agent
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

        print(f"[AutoTitle] Starting for conv {conversation_id} with {config.provider}/{config.model} (key_id={config.api_key_id})", flush=True)

        key_record = await queries.get_api_key(config.api_key_id)
        if not key_record:
            print(f"[AutoTitle] No API key found for key_id={config.api_key_id}", flush=True)
            return
        api_key = decrypt(key_record.key_encrypted)
        print(f"[AutoTitle] Key decrypted, calling {config.provider}/{config.model}...", flush=True)

        provider = get_provider(config.provider)

        # DeepSeek needs headroom for reasoning tokens; other providers are fine with 30
        title_max_tokens = 2000 if config.provider == "deepseek" else 30

        request = LLMRequest(
            model=config.model,
            api_key=api_key,
            system_prompt="Generate a SHORT title (max 6 words) summarizing the user's message. Reply with ONLY the title, no quotes.",
            messages=[{"role": "user", "content": first_message}],
            max_tokens=title_max_tokens,
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
    agents = await queries.list_agents()

    config_map = {c.id: f"{c.provider}/{c.model}" for c in configs}
    agent_map = {a.id: a.name for a in agents}
    avatar_map = {a.id: a.avatar_index for a in agents}
    enriched = []
    for msg in messages:
        enriched.append({
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "role": msg.role,
            "llm_config_id": msg.llm_config_id,
            "agent_id": msg.agent_id,
            "content": msg.content,
            "created_at": msg.created_at,
            "llm_name": agent_map.get(msg.agent_id, "") if msg.agent_id else config_map.get(msg.llm_config_id, "") if msg.llm_config_id else "",
            "avatar_idx": avatar_map.get(msg.agent_id, msg.llm_config_id or 0) if msg.agent_id else (msg.llm_config_id or 0) % 8,
        })

    return templates.TemplateResponse(
        request,
        "fragments/messages.html",
        {"request": request, "locale": locale, "strings": strings,
         "conversation": conversation, "messages": enriched,
         "llm_count": len(agents), "agents": agents},
    )


@router.post("/fragments/conversations/{conversation_id}/messages", response_class=HTMLResponse)
async def fragment_post_message(conversation_id: int, content: str = Form(...)):
    configs = await queries.list_llm_configs()
    agents_list = await queries.list_agents()

    # Save user message
    user_msg = await queries.create_message(conversation_id, "user", content)

    # #1: Auto-title generation — only if conversation has no title yet and first user message
    all_msgs = await queries.get_messages(conversation_id)
    user_count = sum(1 for m in all_msgs if m.role == "user")
    conv = await queries.get_conversation(conversation_id)
    title_empty = not conv or not conv.title
    print(f"[AutoTitle] Check: user_count={user_count}, title_empty={title_empty}, configs={len(configs)}", flush=True)
    if user_count == 1 and title_empty and configs:
        # Use the LLM flagged as title generator, or fall back to first available
        title_llm = next((c for c in configs if c.is_title_generator), None)
        if not title_llm:
            title_llm = configs[0] if configs else None
        if title_llm:
            title_agent = next((a for a in agents_list if a.llm_config_id == title_llm.id), None)
            if title_agent:
                asyncio.create_task(_auto_title(conversation_id, content, title_llm))

    # Determine which agents will respond
    responding = [a for a in agents_list if should_respond(a, content)]

    # Build HTML: user message + placeholders for each responding agent
    # Placeholder IDs are unique per message to prevent cross-message merging
    html_parts = [f'<div class="message user" id="msg-{user_msg.id}">'
                  f'<div class="message-body"><div class="message-bubble">{escape(user_msg.content)}</div>'
                  f'</div></div>']

    for agent in responding:
        placeholder_id = f"placeholder-{agent.id}-{user_msg.id}"
        avatar_class = f"avatar-{agent.avatar_index}"
        html_parts.append(
            f'<div class="message llm generating" id="{placeholder_id}">'
            f'<div class="message-avatar {avatar_class}">{agent.name[0]}</div>'
            f'<div class="message-body">'
            f'<div class="message-sender">{escape(agent.name)}</div>'
            f'<div class="message-bubble">generating...</div>'
            f'</div></div>'
        )

    # Embed SSE connector script directly in the response
    msg_id = user_msg.id  # used in placeholder IDs for uniqueness
    html_parts.append(f'''<script>
        (function() {{
            const MSG_ID = {msg_id};
            if (window.__sseConnection) {{ window.__sseConnection.close(); }}
            const es = new EventSource("/stream/conversations/{conversation_id}");
            window.__sseConnection = es;
            es.addEventListener("token", function(e) {{
                const data = JSON.parse(e.data);
                const el = document.getElementById("placeholder-" + data.agent_id + "-" + MSG_ID);
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
                const el = document.getElementById("placeholder-" + data.agent_id + "-" + MSG_ID);
                if (el) {{
                    el.classList.remove("generating");
                    const bubble = el.querySelector(".message-bubble");
                    if (bubble && data.content) {{
                        bubble.innerHTML = DOMPurify.sanitize(marked.parse(data.content));
                        bubble.classList.add("rendered");
                    }}
                }}
            }});
            es.addEventListener("llm-error", function(e) {{
                const data = JSON.parse(e.data);
                const el = document.getElementById("placeholder-" + data.agent_id + "-" + MSG_ID);
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


@router.delete("/fragments/conversations/{conversation_id}")
async def fragment_delete_conversation(conversation_id: int, request: Request):
    await queries.delete_conversation(conversation_id)
    # Refresh the sidebar and redirect to home
    locale = get_locale(request)
    strings = get_strings(locale)
    conversations = await queries.list_conversations()
    response = templates.TemplateResponse(
        request,
        "fragments/conversations.html",
        {"request": request, "locale": locale, "strings": strings, "conversations": conversations},
    )
    response.headers["HX-Refresh"] = "true"
    return response


@router.put("/fragments/conversations/{conversation_id}/title")
async def fragment_update_title(conversation_id: int, title: str = Form(...)):
    await queries.update_conversation_title(conversation_id, title)
    # Return both the sidebar title span AND an OOB swap for the header title
    return HTMLResponse(f'''<span id="conv-title-{conversation_id}">{title}</span>
<span id="conversation-title-text" hx-swap-oob="true">{title}</span>''')


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
    provider: str = Form(...),
    model: str = Form(...),
    api_key_id: int = Form(...),
):
    config = LLMConfig(
        provider=provider, model=model, api_key_id=api_key_id,
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


@router.put("/fragments/llm-configs/{config_id}", response_class=HTMLResponse)
async def fragment_update_llm_config(
    request: Request,
    config_id: int,
    model: str = Form(...),
    api_key_id: int = Form(...),
    is_title_generator: str = Form("false"),
):
    is_title = is_title_generator in ("true", "on", "1")
    if is_title:
        # Mutual exclusion: uncheck all other configs
        all_configs = await queries.list_llm_configs()
        for c in all_configs:
            if c.id != config_id and c.is_title_generator:
                c.is_title_generator = False
                await queries.update_llm_config(c)

    config = await queries.get_llm_config(config_id)
    if config:
        config.model = model
        config.api_key_id = api_key_id
        config.is_title_generator = is_title
        await queries.update_llm_config(config)
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


# --- Agent routes ---

@router.get("/fragments/agents", response_class=HTMLResponse)
async def fragment_agents(request: Request):
    locale = get_locale(request)
    strings = get_strings(locale)
    agents = await queries.list_agents()
    llm_configs = await queries.list_llm_configs()
    llm_map = {c.id: c for c in llm_configs}
    return templates.TemplateResponse(
        request,
        "fragments/agents.html",
        {"request": request, "locale": locale, "strings": strings,
         "agents": agents, "llm_configs": llm_configs, "llm_map": llm_map},
    )


@router.post("/fragments/agents", response_class=HTMLResponse)
async def fragment_create_agent(
    request: Request,
    name: str = Form(...),
    llm_config_id: int = Form(...),
    system_prompt: str = Form(""),
    style_preset: str = Form("custom"),
    participation_mode: str = Form("mention_only"),
    avatar_index: int = Form(0),
):
    agent = Agent(
        name=name, llm_config_id=llm_config_id,
        system_prompt=system_prompt, style_preset=style_preset,
        participation_mode=participation_mode, avatar_index=avatar_index,
    )
    await queries.create_agent(agent)
    locale = get_locale(request)
    strings = get_strings(locale)
    agents = await queries.list_agents()
    llm_configs = await queries.list_llm_configs()
    llm_map = {c.id: c for c in llm_configs}
    return templates.TemplateResponse(
        request,
        "fragments/agents.html",
        {"request": request, "locale": locale, "strings": strings,
         "agents": agents, "llm_configs": llm_configs, "llm_map": llm_map},
    )


@router.put("/fragments/agents/{agent_id}", response_class=HTMLResponse)
async def fragment_update_agent(
    request: Request,
    agent_id: int,
    name: str = Form(...),
    llm_config_id: int = Form(...),
    system_prompt: str = Form(""),
    style_preset: str = Form("custom"),
    participation_mode: str = Form(...),
    avatar_index: int = Form(0),
):
    agent = await queries.get_agent(agent_id)
    if agent:
        agent.name = name
        agent.llm_config_id = llm_config_id
        agent.system_prompt = system_prompt
        agent.style_preset = style_preset
        agent.participation_mode = participation_mode
        agent.avatar_index = avatar_index
        await queries.update_agent(agent)
    locale = get_locale(request)
    strings = get_strings(locale)
    agents = await queries.list_agents()
    llm_configs = await queries.list_llm_configs()
    llm_map = {c.id: c for c in llm_configs}
    return templates.TemplateResponse(
        request,
        "fragments/agents.html",
        {"request": request, "locale": locale, "strings": strings,
         "agents": agents, "llm_configs": llm_configs, "llm_map": llm_map},
    )


@router.delete("/fragments/agents/{agent_id}")
async def fragment_delete_agent(agent_id: int):
    await queries.delete_agent(agent_id)
    return Response(status_code=200)


@router.post("/fragments/settings/language")
async def fragment_set_language(lang: str = Form(...)):
    response = Response(status_code=200)
    response.set_cookie("lang", lang)
    response.headers["HX-Refresh"] = "true"
    return response
