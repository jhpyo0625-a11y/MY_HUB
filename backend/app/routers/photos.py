import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..auth import require_auth
from ..config import settings
from ..photo_extraction import PHOTO_KINDS, extract_from_photo

router = APIRouter(prefix="/api/photos", tags=["photos"],
                   dependencies=[Depends(require_auth)])

_EXT_BY_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _photo_dir() -> Path:
    d = settings.myhub_data_dir / "photos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_photo(image_bytes: bytes, mime: str) -> str:
    ext = _EXT_BY_MIME.get(mime)
    if ext is None:
        raise ValueError(f"지원하지 않는 이미지 형식: {mime}")
    filename = f"{uuid.uuid4().hex}.{ext}"
    (_photo_dir() / filename).write_bytes(image_bytes)
    return filename


@router.post("/extract")
async def extract(kind: str = Form(...), file: UploadFile = File(...)):
    if kind not in PHOTO_KINDS:
        raise HTTPException(422, "알 수 없는 사진 종류입니다")
    image_bytes = await file.read()
    try:
        photo_path = save_photo(image_bytes, file.content_type or "")
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    extracted: dict | None = None
    error: str | None = None
    try:
        extracted = extract_from_photo(kind, image_bytes, file.content_type)
    except Exception as exc:  # bad JSON, network error, model refusal
        error = str(exc)

    return {"photo_path": photo_path, "extracted": extracted, "error": error}


@router.get("/{filename}")
def get_photo(filename: str):
    photo_root = _photo_dir().resolve()
    candidate = (photo_root / filename).resolve()
    if not candidate.is_relative_to(photo_root) or not candidate.is_file():
        raise HTTPException(404, "사진을 찾을 수 없습니다")
    return FileResponse(candidate)
