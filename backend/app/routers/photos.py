import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..auth import require_auth
from ..config import settings
from ..photo_extraction import PHOTO_KINDS, extract_from_photo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/photos", tags=["photos"],
                   dependencies=[Depends(require_auth)])

_EXT_BY_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 10MB


def _photo_dir() -> Path:
    d = settings.myhub_data_dir / "photos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _looks_like(mime: str, data: bytes) -> bool:
    # Client-supplied Content-Type is trivially spoofable — check the real
    # file signature before trusting the extension we're about to write.
    if mime == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def save_photo(image_bytes: bytes, mime: str) -> str:
    ext = _EXT_BY_MIME.get(mime)
    if ext is None:
        raise ValueError(f"지원하지 않는 이미지 형식: {mime}")
    if not _looks_like(mime, image_bytes):
        raise ValueError("이미지 파일이 손상되었거나 형식이 올바르지 않습니다")
    filename = f"{uuid.uuid4().hex}.{ext}"
    (_photo_dir() / filename).write_bytes(image_bytes)
    return filename


async def _read_capped(file: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1 << 16)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(413, "이미지 파일이 너무 큽니다 (최대 10MB)")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/extract")
async def extract(kind: str = Form(...), file: UploadFile = File(...)):
    if kind not in PHOTO_KINDS:
        raise HTTPException(422, "알 수 없는 사진 종류입니다")
    image_bytes = await _read_capped(file, MAX_PHOTO_BYTES)
    try:
        photo_path = save_photo(image_bytes, file.content_type or "")
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    extracted: dict | None = None
    error: str | None = None
    try:
        extracted = extract_from_photo(kind, image_bytes, file.content_type)
    except Exception as exc:  # bad JSON, network error, model refusal
        logger.warning("photo extraction failed for kind=%s", kind, exc_info=True)
        error = str(exc)

    return {"photo_path": photo_path, "extracted": extracted, "error": error}


@router.get("/{filename}")
def get_photo(filename: str):
    photo_root = _photo_dir().resolve()
    candidate = (photo_root / filename).resolve()
    if not candidate.is_relative_to(photo_root) or not candidate.is_file():
        raise HTTPException(404, "사진을 찾을 수 없습니다")
    return FileResponse(candidate)
