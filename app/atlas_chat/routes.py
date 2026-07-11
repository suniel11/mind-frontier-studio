from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.atlas_chat.engine import answer_message
from app.atlas_chat.models import AtlasChatClearRequest, AtlasChatRequest
from app.atlas_chat.store import (
    clear_conversation,
    get_messages,
    list_conversations,
)
from app.core.settings import settings

router = APIRouter(prefix="/chat", tags=["Atlas Conversation"])


@router.post("/ask")
def chat_ask(payload: AtlasChatRequest):
    return answer_message(
        settings.root,
        payload.message,
        payload.conversation_id,
    )


@router.get("/conversations")
def chat_conversations(limit: int = 30):
    return {"conversations": list_conversations(settings.root, limit)}


@router.get("/conversations/{conversation_id}")
def chat_conversation(conversation_id: str):
    messages = get_messages(settings.root, conversation_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {
        "conversation_id": conversation_id,
        "messages": messages,
    }


@router.post("/clear")
def chat_clear(payload: AtlasChatClearRequest):
    removed = clear_conversation(
        settings.root,
        payload.conversation_id,
    )
    if not removed:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"ok": True}
