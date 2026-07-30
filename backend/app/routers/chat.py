import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import require_auth
from ..chat import send_chat_message
from ..db import get_db
from ..models import ChatMessage

router = APIRouter(prefix="/api/chat", tags=["chat"],
                   dependencies=[Depends(require_auth)])


def _msg_to_dict(m: ChatMessage) -> dict:
    return {
        "id": m.id, "role": m.role, "content": m.content,
        "proposed_entries": json.loads(m.proposed_entries) if m.proposed_entries else [],
        "created_at": m.created_at.isoformat(),
    }


@router.get("/messages")
def list_messages(db: Session = Depends(get_db)):
    msgs = db.query(ChatMessage).order_by(ChatMessage.created_at).all()
    return [_msg_to_dict(m) for m in msgs]


class MessageIn(BaseModel):
    content: str


@router.post("/messages", status_code=201)
def post_message(body: MessageIn, db: Session = Depends(get_db)):
    user_msg, assistant_msg = send_chat_message(db, body.content)
    return {"user_message": _msg_to_dict(user_msg),
            "assistant_message": _msg_to_dict(assistant_msg)}
