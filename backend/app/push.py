import json
import logging
from urllib.parse import urlparse

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from .config import settings
from .models import Profile

logger = logging.getLogger(__name__)

# The reminder scheduler POSTs to a stored subscription's `endpoint` once a
# minute, unattended — an unvalidated client-supplied URL would make that a
# persistent SSRF beacon. Restrict to the actual browser push vendors.
_ALLOWED_PUSH_HOSTS = (
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "notify.windows.com",
    "push.apple.com",
)
_PUSH_TIMEOUT = 10.0


def _endpoint_allowed(endpoint: str) -> bool:
    host = (urlparse(endpoint).hostname or "").lower()
    return any(host == h or host.endswith(f".{h}") for h in _ALLOWED_PUSH_HOSTS)


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
    endpoint = subscription.get("endpoint", "")
    if not _endpoint_allowed(endpoint):
        raise ValueError(f"지원하지 않는 푸시 서비스입니다: {endpoint}")
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
            timeout=_PUSH_TIMEOUT,
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
