import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from .config import settings
from .models import Profile

logger = logging.getLogger(__name__)


def get_subscription(db: Session) -> dict | None:
    profile = db.get(Profile, 1)
    if profile is None or not profile.push_subscription:
        return None
    try:
        return json.loads(profile.push_subscription)
    except json.JSONDecodeError:
        logger.warning("stored push_subscription is not valid JSON", exc_info=True)
        return None


def subscribe(db: Session, subscription: dict) -> None:
    profile = db.get(Profile, 1)
    if profile is None:
        profile = Profile(id=1)
        db.add(profile)
    profile.push_subscription = json.dumps(subscription)
    db.commit()


def unsubscribe(db: Session) -> None:
    profile = db.get(Profile, 1)
    if profile is not None:
        profile.push_subscription = None
        db.commit()


def send_push(db: Session, payload: dict) -> bool:
    subscription = get_subscription(db)
    if subscription is None:
        return False
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )
        return True
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):  # subscription gone — stop until re-subscribed
            unsubscribe(db)
        else:
            logger.warning("push send failed", exc_info=True)
        return False
    except Exception:
        logger.warning("push send failed", exc_info=True)
        return False
