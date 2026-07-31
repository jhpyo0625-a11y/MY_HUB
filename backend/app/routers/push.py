from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import require_auth
from ..config import settings
from ..db import get_db
from ..push import subscribe, unsubscribe

router = APIRouter(prefix="/api/push", tags=["push"],
                   dependencies=[Depends(require_auth)])


@router.get("/vapid-public-key")
def vapid_public_key():
    return {"key": settings.vapid_public_key}


class SubscribeIn(BaseModel):
    subscription: dict


@router.post("/subscribe")
def do_subscribe(body: SubscribeIn, db: Session = Depends(get_db)):
    subscribe(db, body.subscription)
    return {"ok": True}


@router.delete("/subscribe")
def do_unsubscribe(db: Session = Depends(get_db)):
    unsubscribe(db)
    return {"ok": True}
