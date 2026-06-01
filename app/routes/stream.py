import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

_streams: dict[int, asyncio.Queue] = {}


def get_or_create_queue(conversation_id: int) -> asyncio.Queue:
    if conversation_id not in _streams:
        _streams[conversation_id] = asyncio.Queue()
    return _streams[conversation_id]


def remove_queue(conversation_id: int) -> None:
    _streams.pop(conversation_id, None)


async def event_generator(conversation_id: int, request: Request):
    queue = get_or_create_queue(conversation_id)
    print(f"[SSE] Connection opened for conversation {conversation_id}", flush=True)
    quiet_count = 0
    while True:
        if await request.is_disconnected():
            print(f"[SSE] Client disconnected for conversation {conversation_id}", flush=True)
            break
        try:
            event = await asyncio.wait_for(queue.get(), timeout=5.0)
            quiet_count = 0
            event_type = event["type"]
            payload = json.dumps({k: v for k, v in event.items() if k != "type"})
            print(f"[SSE] Sending {event_type} for llm_config_id={event.get('llm_config_id')}", flush=True)
            yield f"event: {event_type}\ndata: {payload}\n\n"
        except asyncio.TimeoutError:
            quiet_count += 1
            if quiet_count >= 2:
                print(f"[SSE] Closing idle connection for conversation {conversation_id}", flush=True)
                break


@router.get("/stream/conversations/{conversation_id}")
async def stream_conversation(conversation_id: int, request: Request):
    return StreamingResponse(
        event_generator(conversation_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
