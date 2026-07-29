import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from pydantic import BaseModel

from .config import settings

COOKIE_NAME = "myhub_session"
MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def _signer() -> TimestampSigner:
    return TimestampSigner(settings.myhub_secret_key)


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginIn, response: Response):
    if not secrets.compare_digest(body.password, settings.myhub_password):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다")
    token = _signer().sign(b"ok").decode()
    response.set_cookie(COOKIE_NAME, token, max_age=MAX_AGE,
                        httponly=True, samesite="lax",
                        secure=settings.myhub_cookie_secure)
    return {"ok": True}


def require_auth(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    try:
        _signer().unsign(token, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="세션이 만료되었습니다")


@router.get("/me", dependencies=[Depends(require_auth)])
def me():
    return {"ok": True}


# --- profile (single row, id=1) ---
from datetime import date as date_type  # noqa: E402

from sqlalchemy.orm import Session  # noqa: E402

from .db import get_db  # noqa: E402
from .models import Profile  # noqa: E402

profile_router = APIRouter(prefix="/api/profile", tags=["profile"],
                           dependencies=[Depends(require_auth)])


class ProfileIn(BaseModel):
    name: str = ""
    sex: str | None = None          # "M" | "F"
    birth_date: date_type | None = None


def _get_or_create(db: Session) -> Profile:
    p = db.get(Profile, 1)
    if p is None:
        p = Profile(id=1)
        db.add(p)
        db.commit()
    return p


@profile_router.get("")
def get_profile(db: Session = Depends(get_db)):
    p = _get_or_create(db)
    return {"name": p.name, "sex": p.sex,
            "birth_date": p.birth_date.isoformat() if p.birth_date else None}


@profile_router.put("")
def put_profile(body: ProfileIn, db: Session = Depends(get_db)):
    p = _get_or_create(db)
    p.name, p.sex, p.birth_date = body.name, body.sex, body.birth_date
    db.commit()
    return {"name": p.name, "sex": p.sex,
            "birth_date": p.birth_date.isoformat() if p.birth_date else None}
