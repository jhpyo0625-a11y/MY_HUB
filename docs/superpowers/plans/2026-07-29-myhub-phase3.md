# MyHub Phase 3 — Eyes and Voice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add photo-based data entry (supplement labels, meal photos, health-checkup sheets, nutrition-facts labels), a conversational AI assistant that proposes structured saves, and web-push supplement reminders — on top of the Phase 1/2 logging + intelligence backbone.

**Architecture:** Three independent subsystems layered onto the existing FastAPI/SQLite backend and React SPA. (1) A shared photo-extraction module calls the vision-capable mini model with a kind-specific prompt, and existing create endpoints (meals, supplements, metrics) gain optional fields to accept the extracted data after user confirmation. (2) A chat engine assembles a system prompt from the latest analysis + evidence + missing-data list, calls the strong model with conversation history, and validates a JSON reply schema that may propose metric saves. (3) A pure, testable reminder-check function compares active supplement schedules against the current time and sends web push via `pywebpush`, deduped by a per-day log table; APScheduler ticks it every minute.

**Tech Stack:** Same as Phase 1/2 (FastAPI, SQLAlchemy 2.x, SQLite, pytest, OpenAI SDK · React + Vite + TS + Tailwind v4) plus `python-multipart` (file uploads), `pywebpush` + its `py_vapid` dependency (web push), `apscheduler` (reminder ticking). No new frontend npm dependencies — service worker and push registration use native browser APIs.

**Spec:** `docs/superpowers/specs/2026-07-29-myhub-design.md` §3 (chat_messages), §4.1 (photo pipeline), §4.5 (reminders), §4.6 (chat), §6 (error handling), §8 tasks 10–12.

**Scope notes (deviations, deliberate):**
- Push enable/disable lives inline on 대시보드 as a small card, not a separate 설정 page. The spec's 5-page table (§5) has no settings page, and one isn't worth inventing for a single toggle. `# ponytail: move to a dedicated settings page if more device/notification controls show up later.`
- Full PWA installability (manifest.json, install prompt) is explicitly **Phase 4 item 14** ("PWA install flow"). This plan ships only the service worker needed for push delivery — no manifest, no install banner.
- Chat's "cites only evidence_refs" rule (spec §4.6) is enforced at the prompt level only, unlike the analysis engine's machine-validated citation check (Phase 2). The spec doesn't require schema-level citation validation for chat, and conversational turns are lower-stakes than the stored report.
- Dashboard missing-data prompt cards (spec §4.6 "second surface") already shipped in Phase 2's `MissingDataCard` (`frontend/src/pages/DashboardPage.tsx`). Nothing to add here.
- VAPID keypair generation is a manual one-time ops step (like `MYHUB_PASSWORD`), not automated in code.

## Global Constraints (Phase 3 additions on top of Phase 1/2's)

- All new `/api/*` routes require `require_auth` (`dependencies=[Depends(require_auth)]` on the router), same as every existing router.
- `Base.metadata.create_all` only — no migrations. `ChatMessage` and `ReminderLog` are pure additions.
- Photos are never public: served only via the authenticated `GET /api/photos/{filename}` route, never through the static SPA mount.
- Photo files are saved to disk **before** extraction runs and **regardless of extraction success** — a failed GPT-vision call must never lose the user's photo (spec §6: "Photo extraction nonsense → Confirmation screen — user edits or discards").
- `nutrient_source` vocabulary (on `MealItem`) grows from `mfds_db | ai_estimate | none` to include `photo` (nutrition-label extraction, values used verbatim). `MetricEntry.source` already supports `manual | photo` (Phase 1 comment) — the new bulk endpoint uses `photo`.
- Mock OpenAI in tests the same way `test_nutrition.py`/`test_analysis.py` already do: `monkeypatch.setattr(<module>, "OpenAI", FakeClientClass)`, never hit the network.
- Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` (repo convention from Phase 1/2).
- Dev runs unchanged: `cd backend; .venv\Scripts\uvicorn app.main:app --reload --port 8000` / `cd frontend; npm run dev`.

## File Structure (Phase 3 additions)

```
backend/
  requirements.txt        # + python-multipart, pywebpush, apscheduler
  app/
    config.py             # + photo/VAPID settings
    models.py             # + ChatMessage, ReminderLog
    photo_extraction.py   # NEW — vision prompts per kind
    chat.py                # NEW — system prompt + LLM call + validation
    push.py                # NEW — subscribe/unsubscribe/send_push
    reminders.py            # NEW — check_and_send_reminders(db, now)
    main.py                # + photos/chat/push routers, scheduler wiring
    routers/
      photos.py            # NEW
      chat.py               # NEW
      push.py               # NEW
      meals.py              # + photo_path, prefilled nutrients
      supplements.py        # + photo_path
      metrics.py            # + bulk entries endpoint
  tests/
    test_photos.py, test_chat.py, test_push.py, test_reminders.py   # NEW
    test_meals.py, test_supplements.py, test_metrics.py              # appended
frontend/
  public/sw.js             # NEW — push + notificationclick handlers
  src/
    api.ts                 # + apiUpload
    push.ts                 # NEW — subscribe/unsubscribe helpers
    PhotoUpload.tsx          # NEW — shared upload button + photoUrl()
    App.tsx                  # + 채팅 tab/route
    pages/
      ChatPage.tsx            # NEW
      CalendarPage.tsx        # + meal/nutrition-label photo wiring
      SupplementsPage.tsx     # + supplement-label photo wiring
      MyDataPage.tsx          # + lab-result bulk-entry photo wiring
      DashboardPage.tsx       # + push enable/disable card
```

---

### Task 1: Photo storage + vision extraction + upload/serve endpoints

**Files:**
- Modify: `backend/requirements.txt` (add `python-multipart>=0.0.9`)
- Create: `backend/app/photo_extraction.py`
- Create: `backend/app/routers/photos.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_photos.py`

**Interfaces:**
- Consumes: `settings` from `app.config`; `NUTRIENT_KEYS` from `app.nutrition`; `METRIC_DEFINITIONS` from `app.seed`.
- Produces: `PHOTO_KINDS: set[str]` = `{"supplement_label", "meal", "lab_result", "nutrition_label"}`; `extract_from_photo(kind: str, image_bytes: bytes, mime: str) -> dict` (raises `ValueError`/propagates on failure); `save_photo(image_bytes: bytes, mime: str) -> str` (returns bare filename, e.g. `"<uuid>.jpg"`); `POST /api/photos/extract` (multipart `kind` + `file`) → `{"photo_path": str, "extracted": dict | None, "error": str | None}`; `GET /api/photos/{filename}` → the image file, 404 if missing. Later tasks store the returned `photo_path` (bare filename) directly on `Meal.photo_path`/`Supplement.photo_path` and build display URLs as `/api/photos/{photo_path}`.

- [ ] **Step 1: Add python-multipart to requirements**

Append to `backend/requirements.txt`:
```
python-multipart>=0.0.9
```
```powershell
cd backend; .venv\Scripts\pip install -r requirements.txt
```

- [ ] **Step 2: Write failing tests**

`backend/tests/test_photos.py`:
```python
import io
import json


def _fake_client(payload):
    class FakeMsg:
        content = json.dumps(payload)
    class FakeChoice:
        message = FakeMsg()
    class FakeCompletion:
        choices = [FakeChoice()]
    class FakeCompletions:
        def create(self, **kw):
            return FakeCompletion()
    class FakeChat:
        completions = FakeCompletions()
    class FakeClient:
        def __init__(self, **kw): self.chat = FakeChat()
    return FakeClient


def test_extract_supplement_label(auth_client, monkeypatch, tmp_path):
    from app import photo_extraction
    from app.config import settings
    monkeypatch.setattr(settings, "myhub_data_dir", tmp_path)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    payload = {"brand": "나우푸드", "product_name": "오메가3", "serving_size": "1캡슐",
               "ingredients": [{"ingredient_code": "omega3", "amount": 1000, "unit": "mg"}]}
    monkeypatch.setattr(photo_extraction, "OpenAI", _fake_client(payload))

    res = auth_client.post("/api/photos/extract",
                           data={"kind": "supplement_label"},
                           files={"file": ("label.jpg", io.BytesIO(b"fake-bytes"), "image/jpeg")})
    assert res.status_code == 200
    body = res.json()
    assert body["extracted"]["product_name"] == "오메가3"
    assert body["error"] is None
    assert body["photo_path"].endswith(".jpg")

    photo_res = auth_client.get(f"/api/photos/{body['photo_path']}")
    assert photo_res.status_code == 200
    assert photo_res.content == b"fake-bytes"


def test_extract_unknown_kind_rejected(auth_client):
    res = auth_client.post("/api/photos/extract",
                           data={"kind": "nonsense"},
                           files={"file": ("x.jpg", io.BytesIO(b"x"), "image/jpeg")})
    assert res.status_code == 422


def test_extract_unsupported_mime_rejected(auth_client):
    res = auth_client.post("/api/photos/extract",
                           data={"kind": "meal"},
                           files={"file": ("x.gif", io.BytesIO(b"x"), "image/gif")})
    assert res.status_code == 422


def test_extract_llm_failure_still_saves_photo(auth_client, monkeypatch, tmp_path):
    from app import photo_extraction
    from app.config import settings
    monkeypatch.setattr(settings, "myhub_data_dir", tmp_path)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class BoomClient:
        def __init__(self, **kw):
            class C:
                def create(self, **kw): raise RuntimeError("vision API down")
            class Ch:
                completions = C()
            self.chat = Ch()
    monkeypatch.setattr(photo_extraction, "OpenAI", BoomClient)

    res = auth_client.post("/api/photos/extract",
                           data={"kind": "meal"},
                           files={"file": ("m.jpg", io.BytesIO(b"data"), "image/jpeg")})
    assert res.status_code == 200
    body = res.json()
    assert body["extracted"] is None
    assert "vision API down" in body["error"]
    assert body["photo_path"]


def test_photo_not_found(auth_client):
    assert auth_client.get("/api/photos/does-not-exist.jpg").status_code == 404


def test_photos_require_auth(client):
    assert client.get("/api/photos/x.jpg").status_code == 401
```

- [ ] **Step 3: Run tests, verify fail**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/test_photos.py -v
```
Expected: FAIL — `ModuleNotFoundError: app.photo_extraction` / 404s.

- [ ] **Step 4: Implement extraction module**

`backend/app/photo_extraction.py`:
```python
import base64
import json
import logging

from openai import OpenAI

from .config import settings
from .nutrition import NUTRIENT_KEYS
from .seed import METRIC_DEFINITIONS

logger = logging.getLogger(__name__)

PHOTO_KINDS = {"supplement_label", "meal", "lab_result", "nutrition_label"}

# Kept in sync with SupplementsPage.tsx's INGREDIENT_SUGGESTIONS by hand —
# small fixed vocabulary, not worth a shared-codegen step.
INGREDIENT_CODE_HINTS = [
    "vitamin_a", "vitamin_b1", "vitamin_b2", "vitamin_b6", "vitamin_b12",
    "vitamin_c", "vitamin_d", "vitamin_e", "vitamin_k", "folate", "niacin",
    "biotin", "calcium", "magnesium", "zinc", "iron", "selenium", "potassium",
    "omega3", "lutein", "probiotics", "coenzyme_q10", "milk_thistle",
]

_LAB_METRIC_CODES = [
    (code, name_ko) for code, name_ko, _unit, domain, _input_type, _lo, _hi
    in METRIC_DEFINITIONS if domain in ("body", "lab")
]


def _prompt_for(kind: str) -> str:
    if kind == "supplement_label":
        return (
            "이 영양제 라벨 사진에서 정보를 추출해 JSON으로만 답하세요. "
            'JSON 형식: {"brand": str, "product_name": str, "serving_size": str, '
            '"ingredients": [{"ingredient_code": str, "amount": number, "unit": str}]}. '
            f"ingredient_code는 가능하면 다음 중에서 고르세요: {', '.join(INGREDIENT_CODE_HINTS)}. "
            "일치하는 항목이 없으면 영문 소문자 스네이크케이스로 새로 만드세요. "
            "읽을 수 없는 값은 생략하세요."
        )
    if kind == "meal":
        return (
            "이 음식 사진에서 요리 이름과 재료를 추출해 JSON으로만 답하세요. "
            'JSON 형식: {"dish_name": str, "items": [{"name": str, "amount": str}]}. '
            "amount는 '100g', '반 공기'처럼 짧은 한국어 표현으로 추정하세요."
        )
    if kind == "lab_result":
        codes = ", ".join(f"{c}({n})" for c, n in _LAB_METRIC_CODES)
        return (
            "이 건강검진 결과지 사진에서 수치를 추출해 JSON으로만 답하세요. "
            'JSON 형식: {"entries": [{"metric_code": str, "value_num": number, '
            '"measured_at": str}]}. '
            f"metric_code는 반드시 다음 중에서만 고르세요: {codes}. "
            "measured_at은 검사일이 보이면 YYYY-MM-DD, 없으면 빈 문자열. "
            "표에 없는 항목은 결과에 포함하지 마세요."
        )
    if kind == "nutrition_label":
        return (
            "이 영양정보표 사진에서 정보를 추출해 JSON으로만 답하세요. "
            'JSON 형식: {"name": str, "amount": str, "nutrients": {키: number}}. '
            f"nutrients의 키는 정확히 다음만 사용: {', '.join(NUTRIENT_KEYS)}. "
            "amount는 1회 제공량 기준(예: '100g'). 읽을 수 없는 값은 생략하세요."
        )
    raise ValueError(f"알 수 없는 사진 종류: {kind}")


def extract_from_photo(kind: str, image_bytes: bytes, mime: str) -> dict:
    if kind not in PHOTO_KINDS:
        raise ValueError(f"알 수 없는 사진 종류: {kind}")
    prompt = _prompt_for(kind)
    b64 = base64.b64encode(image_bytes).decode()
    client = OpenAI(api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url or None,
                    timeout=settings.openai_timeout)
    res = client.chat.completions.create(
        model=settings.openai_model_mini,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }],
        response_format={"type": "json_object"},
    )
    return json.loads(res.choices[0].message.content)
```

- [ ] **Step 5: Implement photos router**

`backend/app/routers/photos.py`:
```python
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
```

- [ ] **Step 6: Wire router into main.py**

In `backend/app/main.py`, change:
```python
    from .routers import analysis, calendar, meals, metrics, safety, supplements
    app.include_router(meals.router)
    app.include_router(metrics.router)
    app.include_router(supplements.router)
    app.include_router(calendar.router)
    app.include_router(safety.router)
    app.include_router(analysis.router)
```
to:
```python
    from .routers import analysis, calendar, meals, metrics, photos, safety, supplements
    app.include_router(meals.router)
    app.include_router(metrics.router)
    app.include_router(supplements.router)
    app.include_router(calendar.router)
    app.include_router(safety.router)
    app.include_router(analysis.router)
    app.include_router(photos.router)
```

- [ ] **Step 7: Run tests, verify pass**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 8: Commit**

```powershell
git add -A
git commit -m "feat: add photo storage, vision extraction, and serving endpoint"
```

---

### Task 2: Wire photo_path + prefilled nutrients into meals/supplements, add bulk metric entries

**Files:**
- Modify: `backend/app/models.py` (comment update only, no schema change)
- Modify: `backend/app/routers/meals.py`, `backend/app/routers/supplements.py`, `backend/app/routers/metrics.py`
- Test: append to `backend/tests/test_meals.py`, `backend/tests/test_supplements.py`, `backend/tests/test_metrics.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `MealIn.photo_path: str | None`, `MealItemIn.nutrients: dict | None` (when set, skips `resolve_nutrients` and stores with `nutrient_source="photo"`); `meal_to_dict` includes `photo_path`; `SupplementIn.photo_path: str | None`, `supp_to_dict` includes `photo_path`; `POST /api/metrics/entries/bulk {entries: [EntryIn]}` → `{"created": [id, ...]}` (all-or-nothing: any unknown `metric_code` → 404, nothing inserted; inserted rows get `source="photo"`).

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_meals.py`:
```python
def test_meal_with_photo_and_prefilled_nutrients(auth_client):
    res = auth_client.post("/api/meals", json={
        "eaten_at": "2026-07-29T12:00:00", "dish_name": "컵라면",
        "photo_path": "abc123.jpg",
        "items": [{"name": "컵라면", "amount": "1개",
                   "nutrients": {"kcal": 500, "sodium_mg": 1200}}]})
    assert res.status_code == 201
    meal = auth_client.get("/api/meals",
                           params={"start": "2026-07-29", "end": "2026-07-29"}).json()[0]
    assert meal["photo_path"] == "abc123.jpg"
    assert meal["items"][0]["nutrient_source"] == "photo"
    assert meal["items"][0]["nutrients"]["kcal"] == 500
```

Append to `backend/tests/test_supplements.py` (reuses the module-level `SUPP` dict already defined there):
```python
def test_supplement_photo_path_roundtrip(auth_client):
    body = dict(SUPP, photo_path="label123.jpg")
    auth_client.post("/api/supplements", json=body)
    supp = auth_client.get("/api/supplements").json()[0]
    assert supp["photo_path"] == "label123.jpg"
```

Append to `backend/tests/test_metrics.py` (reuses the `seeded_client` fixture already defined there):
```python
def test_bulk_entries(seeded_client):
    res = seeded_client.post("/api/metrics/entries/bulk", json={"entries": [
        {"metric_code": "ldl", "value_num": 110, "measured_at": "2026-07-01T00:00:00"},
        {"metric_code": "hdl", "value_num": 55, "measured_at": "2026-07-01T00:00:00"},
    ]})
    assert res.status_code == 201
    assert len(res.json()["created"]) == 2
    latest = seeded_client.get("/api/metrics/latest").json()
    assert latest["ldl"]["value_num"] == 110


def test_bulk_entries_unknown_code_rejects_all(seeded_client):
    res = seeded_client.post("/api/metrics/entries/bulk", json={"entries": [
        {"metric_code": "ldl", "value_num": 110},
        {"metric_code": "nope", "value_num": 1},
    ]})
    assert res.status_code == 404
    assert seeded_client.get("/api/metrics/entries", params={"code": "ldl"}).json() == []
```

- [ ] **Step 2: Run tests, verify fail**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/test_meals.py tests/test_supplements.py tests/test_metrics.py -v
```
Expected: FAIL — `photo_path` missing from responses, 404 on bulk endpoint.

- [ ] **Step 3: Update meals.py**

In `backend/app/routers/meals.py`, change:
```python
class MealItemIn(BaseModel):
    name: str
    amount: str = ""


class MealIn(BaseModel):
    eaten_at: datetime
    dish_name: str
    note: str | None = None
    items: list[MealItemIn] = []


def meal_to_dict(m: Meal) -> dict:
    return {
        "id": m.id,
        "eaten_at": m.eaten_at.isoformat(),
        "dish_name": m.dish_name,
        "note": m.note,
        "items": [{
            "id": i.id, "name": i.name, "amount": i.amount,
            "nutrients": json.loads(i.nutrients) if i.nutrients else None,
            "nutrient_source": i.nutrient_source,
        } for i in m.items],
    }


@router.post("", status_code=201)
def create_meal(body: MealIn, db: Session = Depends(get_db)):
    meal = Meal(eaten_at=body.eaten_at, dish_name=body.dish_name, note=body.note)
    # ponytail: sync resolution; move to background task if saving feels slow
    for it in body.items:
        values, source = resolve_nutrients(it.name, it.amount)
        meal.items.append(MealItem(
            name=it.name, amount=it.amount,
            nutrients=json.dumps(values) if values else None,
            nutrient_source=source))
    db.add(meal)
    db.commit()
    return {"id": meal.id}
```
to:
```python
class MealItemIn(BaseModel):
    name: str
    amount: str = ""
    nutrients: dict | None = None  # pre-filled from nutrition-label photo extraction


class MealIn(BaseModel):
    eaten_at: datetime
    dish_name: str
    note: str | None = None
    photo_path: str | None = None
    items: list[MealItemIn] = []


def meal_to_dict(m: Meal) -> dict:
    return {
        "id": m.id,
        "eaten_at": m.eaten_at.isoformat(),
        "dish_name": m.dish_name,
        "note": m.note,
        "photo_path": m.photo_path,
        "items": [{
            "id": i.id, "name": i.name, "amount": i.amount,
            "nutrients": json.loads(i.nutrients) if i.nutrients else None,
            "nutrient_source": i.nutrient_source,
        } for i in m.items],
    }


@router.post("", status_code=201)
def create_meal(body: MealIn, db: Session = Depends(get_db)):
    meal = Meal(eaten_at=body.eaten_at, dish_name=body.dish_name, note=body.note,
               photo_path=body.photo_path)
    # ponytail: sync resolution; move to background task if saving feels slow
    for it in body.items:
        if it.nutrients is not None:
            values, source = it.nutrients, "photo"
        else:
            values, source = resolve_nutrients(it.name, it.amount)
        meal.items.append(MealItem(
            name=it.name, amount=it.amount,
            nutrients=json.dumps(values) if values else None,
            nutrient_source=source))
    db.add(meal)
    db.commit()
    return {"id": meal.id}
```

- [ ] **Step 4: Update supplements.py**

In `backend/app/routers/supplements.py`, change:
```python
class SupplementIn(BaseModel):
    brand: str = ""
    product_name: str
    serving_size: str = ""
    ingredients: list[IngredientIn] = []
    schedules: list[ScheduleIn] = []


def supp_to_dict(s: Supplement) -> dict:
    return {
        "id": s.id, "brand": s.brand, "product_name": s.product_name,
        "serving_size": s.serving_size, "active": s.active,
        "ingredients": [{"id": i.id, "ingredient_code": i.ingredient_code,
                         "amount": i.amount, "unit": i.unit}
                        for i in s.ingredients],
        "schedules": [{"id": sc.id, "days_of_week": sc.days_of_week,
                       "time_of_day": sc.time_of_day, "servings": sc.servings}
                      for sc in s.schedules],
    }


def _apply(s: Supplement, body: SupplementIn) -> None:
    # ponytail: schedule replacement orphans old intake logs (SQLite has no FK
    # enforcement here) — revisit if adherence stats (Phase 2) need them
    s.brand, s.product_name, s.serving_size = body.brand, body.product_name, body.serving_size
    s.ingredients = [SupplementIngredient(**i.model_dump()) for i in body.ingredients]
    s.schedules = [SupplementSchedule(**sc.model_dump()) for sc in body.schedules]
```
to:
```python
class SupplementIn(BaseModel):
    brand: str = ""
    product_name: str
    serving_size: str = ""
    photo_path: str | None = None
    ingredients: list[IngredientIn] = []
    schedules: list[ScheduleIn] = []


def supp_to_dict(s: Supplement) -> dict:
    return {
        "id": s.id, "brand": s.brand, "product_name": s.product_name,
        "serving_size": s.serving_size, "active": s.active,
        "photo_path": s.photo_path,
        "ingredients": [{"id": i.id, "ingredient_code": i.ingredient_code,
                         "amount": i.amount, "unit": i.unit}
                        for i in s.ingredients],
        "schedules": [{"id": sc.id, "days_of_week": sc.days_of_week,
                       "time_of_day": sc.time_of_day, "servings": sc.servings}
                      for sc in s.schedules],
    }


def _apply(s: Supplement, body: SupplementIn) -> None:
    # ponytail: schedule replacement orphans old intake logs (SQLite has no FK
    # enforcement here) — revisit if adherence stats (Phase 2) need them
    s.brand, s.product_name, s.serving_size = body.brand, body.product_name, body.serving_size
    s.photo_path = body.photo_path
    s.ingredients = [SupplementIngredient(**i.model_dump()) for i in body.ingredients]
    s.schedules = [SupplementSchedule(**sc.model_dump()) for sc in body.schedules]
```

- [ ] **Step 5: Add bulk metrics endpoint**

In `backend/app/routers/metrics.py`, after the existing `create_entry` function, add:
```python
class BulkEntryIn(BaseModel):
    entries: list[EntryIn]


@router.post("/entries/bulk", status_code=201)
def create_entries_bulk(body: BulkEntryIn, db: Session = Depends(get_db)):
    for e in body.entries:
        if db.get(MetricDefinition, e.metric_code) is None:
            raise HTTPException(404, f"알 수 없는 항목입니다: {e.metric_code}")
    created_ids = []
    for e in body.entries:
        entry = MetricEntry(metric_code=e.metric_code, value_num=e.value_num,
                            value_text=e.value_text,
                            measured_at=e.measured_at or datetime.now(),
                            source="photo")
        db.add(entry)
        db.flush()
        created_ids.append(entry.id)
    db.commit()
    return {"created": created_ids}
```

- [ ] **Step 6: Update nutrient_source comment in models.py**

In `backend/app/models.py`, change the `MealItem.nutrient_source` comment from:
```python
    nutrient_source: Mapped[str] = mapped_column(String, default="none")  # mfds_db | ai_estimate | none
```
to:
```python
    nutrient_source: Mapped[str] = mapped_column(String, default="none")  # mfds_db | ai_estimate | photo | none
```

- [ ] **Step 7: Run tests, verify pass**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 8: Commit**

```powershell
git add -A
git commit -m "feat: accept photo-sourced data in meals, supplements, and metric entries"
```

---

### Task 3: Chat engine + model + router

**Files:**
- Modify: `backend/app/models.py` (add `ChatMessage`)
- Create: `backend/app/chat.py`
- Create: `backend/app/routers/chat.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_chat.py`

**Interfaces:**
- Consumes: `Analysis`, `EvidenceRef`, `MetricDefinition` models; `settings`.
- Produces: `ChatMessage(id, role, content, proposed_entries, created_at)` model; `ProposedEntry(BaseModel){metric_code, value_num, value_text}`, `ChatReply(BaseModel){reply, proposed_entries}`; `send_chat_message(db, user_content: str) -> tuple[ChatMessage, ChatMessage]` (user msg, assistant msg — always returns both, falls back to a friendly Korean error string on any LLM/validation failure rather than raising); `GET /api/chat/messages` → list of message dicts; `POST /api/chat/messages {content}` → `{"user_message": {...}, "assistant_message": {...}}`.

- [ ] **Step 1: Write failing tests**

`backend/tests/test_chat.py`:
```python
import json


def _fake_client(payload):
    class FakeMsg:
        content = json.dumps(payload)
    class FakeChoice:
        message = FakeMsg()
    class FakeCompletion:
        choices = [FakeChoice()]
    class FakeCompletions:
        def create(self, **kw):
            return FakeCompletion()
    class FakeChat:
        completions = FakeCompletions()
    class FakeClient:
        def __init__(self, **kw): self.chat = FakeChat()
    return FakeClient


def test_chat_roundtrip(auth_client, monkeypatch):
    from app import chat
    monkeypatch.setattr(chat, "OpenAI",
                        _fake_client({"reply": "네, 알려주셔서 감사해요.",
                                     "proposed_entries": []}))
    monkeypatch.setattr(chat.settings, "openai_api_key", "test-key")

    res = auth_client.post("/api/chat/messages", json={"content": "안녕하세요"})
    assert res.status_code == 201
    body = res.json()
    assert body["user_message"]["content"] == "안녕하세요"
    assert body["assistant_message"]["content"] == "네, 알려주셔서 감사해요."

    listing = auth_client.get("/api/chat/messages").json()
    assert len(listing) == 2
    assert listing[0]["role"] == "user"
    assert listing[1]["role"] == "assistant"


def test_chat_proposes_metric_save(auth_client, db_session_factory, monkeypatch):
    from app import chat
    from app.seed import seed_metric_definitions
    db = db_session_factory()
    seed_metric_definitions(db)
    db.close()

    monkeypatch.setattr(chat, "OpenAI",
                        _fake_client({"reply": "몸무게 72.5kg으로 저장할까요?",
                                     "proposed_entries": [
                                         {"metric_code": "weight_kg", "value_num": 72.5}]}))
    monkeypatch.setattr(chat.settings, "openai_api_key", "test-key")

    res = auth_client.post("/api/chat/messages", json={"content": "몸무게 72.5"})
    proposed = res.json()["assistant_message"]["proposed_entries"]
    assert proposed == [{"metric_code": "weight_kg", "value_num": 72.5, "value_text": None}]


def test_chat_drops_unknown_metric_code(auth_client, monkeypatch):
    from app import chat
    monkeypatch.setattr(chat, "OpenAI",
                        _fake_client({"reply": "저장할게요",
                                     "proposed_entries": [
                                         {"metric_code": "not_real", "value_num": 1}]}))
    monkeypatch.setattr(chat.settings, "openai_api_key", "test-key")

    res = auth_client.post("/api/chat/messages", json={"content": "hi"})
    assert res.json()["assistant_message"]["proposed_entries"] == []


def test_chat_llm_failure_returns_friendly_message(auth_client, monkeypatch):
    from app import chat
    class BoomClient:
        def __init__(self, **kw):
            class C:
                def create(self, **kw): raise RuntimeError("down")
            class Ch: completions = C()
            self.chat = Ch()
    monkeypatch.setattr(chat, "OpenAI", BoomClient)
    monkeypatch.setattr(chat.settings, "openai_api_key", "test-key")

    res = auth_client.post("/api/chat/messages", json={"content": "hi"})
    assert res.status_code == 201
    assert "죄송" in res.json()["assistant_message"]["content"]


def test_chat_requires_auth(client):
    assert client.get("/api/chat/messages").status_code == 401
```

- [ ] **Step 2: Run tests, verify fail**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/test_chat.py -v
```
Expected: FAIL — `ModuleNotFoundError: app.chat`.

- [ ] **Step 3: Add ChatMessage model**

In `backend/app/models.py`, after the `Analysis` class, add:
```python


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String)  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    proposed_entries: Mapped[str | None] = mapped_column(Text)  # JSON list, assistant only
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
```

- [ ] **Step 4: Implement chat engine**

`backend/app/chat.py`:
```python
import json
import logging

from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .config import settings
from .models import Analysis, ChatMessage, EvidenceRef, MetricDefinition

logger = logging.getLogger(__name__)

DISCLAIMER = "이 답변은 의학적 진단이 아닙니다. 심각하거나 지속되는 증상은 전문의와 상담하세요."


class ProposedEntry(BaseModel):
    metric_code: str
    value_num: float | None = None
    value_text: str | None = None


class ChatReply(BaseModel):
    reply: str
    proposed_entries: list[ProposedEntry] = []


def _build_system_prompt(db: Session) -> str:
    latest = db.query(Analysis).order_by(Analysis.run_at.desc()).first()
    analysis_summary = "아직 분석 기록이 없습니다."
    evidence_excerpt: list[dict] = []
    missing_data: list[dict] = []
    if latest:
        result = json.loads(latest.result)
        analysis_summary = result.get("summary", analysis_summary)
        missing_data = result.get("missing_data", [])
        ids: set[int] = set()
        for note in (*result.get("deficiencies", []), *result.get("excesses", [])):
            ids.update(note.get("evidence_ids", []))
        for entry in result.get("top3", []):
            ids.update(entry.get("evidence_ids", []))
        if ids:
            evidence_excerpt = [
                {"id": e.id, "nutrient_code": e.nutrient_code,
                 "claim_summary": e.claim_summary, "reliability_grade": e.reliability_grade}
                for e in db.query(EvidenceRef).filter(EvidenceRef.id.in_(ids)).all()
            ]
    metric_codes = [d.code for d in db.query(MetricDefinition).all()]

    return (
        "당신은 사용자의 건강 데이터를 돕는 친절한 도우미입니다. "
        "반드시 지정된 JSON 스키마로만 답하세요: "
        '{"reply": str, "proposed_entries": '
        '[{"metric_code": str, "value_num": number|null, "value_text": string|null}]}. '
        "규칙: (1) 데이터가 부족하면 한 번에 하나씩, 쉬운 한국어로 질문하세요. "
        "(2) 사용자의 답이 건강 지표 값이면 proposed_entries에 metric_code와 값을 담아 "
        "저장을 제안하세요 (metric_code는 반드시 다음 중에서만: "
        f"{', '.join(metric_codes)}). 값이 아니면 proposed_entries는 빈 배열로 두세요. "
        "(3) 아래 '참고 근거' 목록에 있는 내용만 근거로 말하고, 목록에 없는 의학 정보는 "
        "'잘 모르겠어요, 전문의와 상담해보세요'라고 답하세요. "
        "(4) 모든 텍스트는 자연스러운 한국어로만 작성하세요.\n"
        f"최근 분석 요약: {analysis_summary}\n"
        f"부족한 데이터 목록: {json.dumps(missing_data, ensure_ascii=False)}\n"
        f"참고 근거: {json.dumps(evidence_excerpt, ensure_ascii=False)}\n"
        f"{DISCLAIMER}"
    )


def _call_llm(system_prompt: str, history: list[ChatMessage], user_content: str) -> dict:
    client = OpenAI(api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url or None,
                    timeout=settings.openai_timeout)
    messages = [{"role": "system", "content": system_prompt}]
    for m in history:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_content})
    res = client.chat.completions.create(
        model=settings.openai_model_strong,
        messages=messages,
        response_format={"type": "json_object"},
    )
    return json.loads(res.choices[0].message.content)


def send_chat_message(db: Session, user_content: str) -> tuple[ChatMessage, ChatMessage]:
    history = db.query(ChatMessage).order_by(ChatMessage.created_at).all()
    system_prompt = _build_system_prompt(db)

    user_msg = ChatMessage(role="user", content=user_content)
    db.add(user_msg)
    db.flush()

    valid_codes = {d.code for d in db.query(MetricDefinition).all()}
    try:
        raw = _call_llm(system_prompt, history, user_content)
        parsed = ChatReply.model_validate(raw)
        proposed = [e for e in parsed.proposed_entries if e.metric_code in valid_codes]
        reply_text = parsed.reply
    except Exception:
        logger.warning("chat reply failed", exc_info=True)
        proposed = []
        reply_text = "죄송해요, 지금 답변을 만들지 못했어요. 잠시 후 다시 시도해주세요."

    assistant_msg = ChatMessage(
        role="assistant", content=reply_text,
        proposed_entries=(json.dumps([e.model_dump() for e in proposed])
                          if proposed else None))
    db.add(assistant_msg)
    db.commit()
    return user_msg, assistant_msg
```

- [ ] **Step 5: Implement chat router**

`backend/app/routers/chat.py`:
```python
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
```

- [ ] **Step 6: Wire router into main.py**

In `backend/app/main.py`, change:
```python
    from .routers import analysis, calendar, meals, metrics, photos, safety, supplements
```
to:
```python
    from .routers import analysis, calendar, chat, meals, metrics, photos, safety, supplements
```
and add after `app.include_router(photos.router)`:
```python
    app.include_router(chat.router)
```

- [ ] **Step 7: Run tests, verify pass**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 8: Commit**

```powershell
git add -A
git commit -m "feat: add conversational assistant with structured save proposals"
```

---

### Task 4: Push infrastructure — VAPID settings, subscribe/unsubscribe, send_push

**Files:**
- Modify: `backend/requirements.txt` (add `pywebpush>=2.0`)
- Modify: `backend/app/config.py` (VAPID settings)
- Modify: `backend/app/models.py` (add `ReminderLog`)
- Create: `backend/app/push.py`
- Create: `backend/app/routers/push.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_push.py`

**Interfaces:**
- Produces: `settings.vapid_public_key`, `settings.vapid_private_key`, `settings.vapid_subject`; `ReminderLog(id, schedule_id, date, sent_at)` unique on `(schedule_id, date)`; `get_subscription(db) -> dict | None`, `subscribe(db, subscription: dict) -> None`, `unsubscribe(db) -> None`, `send_push(db, payload: dict) -> bool` (never raises — returns `False` and clears the dead subscription on a 404/410 `WebPushException`); `GET /api/push/vapid-public-key` → `{"key": str}`; `POST /api/push/subscribe {subscription}`; `DELETE /api/push/subscribe`.

- [ ] **Step 1: Add pywebpush to requirements**

Append to `backend/requirements.txt`:
```
pywebpush>=2.0
```
```powershell
cd backend; .venv\Scripts\pip install -r requirements.txt
```

- [ ] **Step 2: Write failing tests**

`backend/tests/test_push.py`:
```python
def test_subscribe_and_unsubscribe(auth_client):
    sub = {"endpoint": "https://push.example.com/abc",
           "keys": {"p256dh": "key1", "auth": "key2"}}
    assert auth_client.post("/api/push/subscribe", json={"subscription": sub}).status_code == 200
    assert auth_client.delete("/api/push/subscribe").status_code == 200


def test_vapid_public_key_endpoint(auth_client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "vapid_public_key", "test-pub-key")
    res = auth_client.get("/api/push/vapid-public-key")
    assert res.json() == {"key": "test-pub-key"}


def test_push_requires_auth(client):
    assert client.get("/api/push/vapid-public-key").status_code == 401


def test_send_push_success(db_session_factory, monkeypatch):
    from app import push
    db = db_session_factory()
    push.subscribe(db, {"endpoint": "https://x", "keys": {"p256dh": "a", "auth": "b"}})

    calls = {}
    def fake_webpush(**kw):
        calls.update(kw)
    monkeypatch.setattr(push, "webpush", fake_webpush)

    ok = push.send_push(db, {"title": "t", "body": "b"})
    assert ok is True
    assert calls["subscription_info"]["endpoint"] == "https://x"


def test_send_push_no_subscription_returns_false(db_session_factory):
    from app import push
    db = db_session_factory()
    assert push.send_push(db, {"title": "t"}) is False


def test_send_push_gone_clears_subscription(db_session_factory, monkeypatch):
    from app import push
    from pywebpush import WebPushException
    db = db_session_factory()
    push.subscribe(db, {"endpoint": "https://x", "keys": {"p256dh": "a", "auth": "b"}})

    class FakeResponse:
        status_code = 410
    def fake_webpush(**kw):
        raise WebPushException("gone", response=FakeResponse())
    monkeypatch.setattr(push, "webpush", fake_webpush)

    assert push.send_push(db, {"title": "t"}) is False
    assert push.get_subscription(db) is None
```

- [ ] **Step 3: Run tests, verify fail**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/test_push.py -v
```
Expected: FAIL — `ModuleNotFoundError: app.push`.

- [ ] **Step 4: Add VAPID settings**

In `backend/app/config.py`, add fields to `Settings` (after `openai_model_strong`):
```python
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"
```

- [ ] **Step 5: Add ReminderLog model**

In `backend/app/models.py`, after the `ChatMessage` class, add:
```python


class ReminderLog(Base):
    __tablename__ = "reminder_logs"
    __table_args__ = (UniqueConstraint("schedule_id", "date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("supplement_schedules.id"))
    date: Mapped[date] = mapped_column(Date)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
```

- [ ] **Step 6: Implement push module**

`backend/app/push.py`:
```python
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
    return json.loads(profile.push_subscription)


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
```

- [ ] **Step 7: Implement push router**

`backend/app/routers/push.py`:
```python
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
```

- [ ] **Step 8: Wire router into main.py**

In `backend/app/main.py`, change:
```python
    from .routers import analysis, calendar, chat, meals, metrics, photos, safety, supplements
```
to:
```python
    from .routers import analysis, calendar, chat, meals, metrics, photos, push, safety, supplements
```
and add after `app.include_router(chat.router)`:
```python
    app.include_router(push.router)
```

- [ ] **Step 9: Run tests, verify pass**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 10: Generate VAPID keypair (one-time ops step, not automated)**

```powershell
cd backend; .venv\Scripts\vapid --gen
```
This is the `py_vapid` console script installed as a `pywebpush` dependency. It writes `private_key.pem`/`public_key.pem` to the current directory and prints an "Application Server Key" (base64url string). `# ponytail: console-script name/output can shift between py_vapid releases — verify against the installed version's output before relying on it, same disclaimer style as nutrition.py's MFDS field mapping.` Set in `.env`:
```
VAPID_PUBLIC_KEY=<printed Application Server Key>
VAPID_PRIVATE_KEY=<path to the generated private_key.pem, e.g. data/vapid_private_key.pem>
```
Move `private_key.pem` into `data/` (outside git) and reference it by path — `pywebpush`'s `vapid_private_key` argument accepts a PEM file path directly.

- [ ] **Step 11: Commit**

```powershell
git add -A
git commit -m "feat: add web push subscribe/unsubscribe and send_push"
```

---

### Task 5: Reminder scheduler (pure check function + APScheduler tick)

**Files:**
- Modify: `backend/requirements.txt` (add `apscheduler>=3.10`)
- Create: `backend/app/reminders.py`
- Modify: `backend/app/main.py` (start/stop scheduler)
- Test: `backend/tests/test_reminders.py`

**Interfaces:**
- Consumes: `send_push` from `app.push` (imported as a module-level name in `reminders.py` so tests can `monkeypatch.setattr(reminders, "send_push", ...)`, matching the `resolve_nutrients` patching convention in `meals.py`).
- Produces: `check_and_send_reminders(db: Session, now: datetime) -> list[int]` (returns the `schedule_id`s processed this call — pure enough to test directly with an injected `now`, no real clock/scheduler needed).

- [ ] **Step 1: Add apscheduler to requirements**

Append to `backend/requirements.txt`:
```
apscheduler>=3.10
```
```powershell
cd backend; .venv\Scripts\pip install -r requirements.txt
```

- [ ] **Step 2: Write failing tests**

`backend/tests/test_reminders.py`:
```python
from datetime import date, datetime


def _make_supp(db_session_factory):
    from app.models import Supplement, SupplementSchedule
    db = db_session_factory()
    s = Supplement(product_name="비타민D")
    s.schedules.append(SupplementSchedule(
        days_of_week="0123456", time_of_day="09:00", servings=1))
    db.add(s)
    db.commit()
    return db, s.schedules[0].id


def test_sends_reminder_when_due(db_session_factory, monkeypatch):
    from app import reminders
    db, schedule_id = _make_supp(db_session_factory)

    sent = []
    monkeypatch.setattr(reminders, "send_push",
                        lambda db, payload: sent.append(payload) or True)

    now = datetime(2026, 7, 29, 9, 0)  # Wed, matches time_of_day
    processed = reminders.check_and_send_reminders(db, now)
    assert processed == [schedule_id]
    assert sent[0]["body"] == "비타민D 드실 시간이에요"

    from app.models import ReminderLog
    assert db.query(ReminderLog).filter_by(
        schedule_id=schedule_id, date=date(2026, 7, 29)).count() == 1


def test_no_duplicate_reminder_same_day(db_session_factory, monkeypatch):
    from app import reminders
    db, _ = _make_supp(db_session_factory)
    monkeypatch.setattr(reminders, "send_push", lambda db, payload: True)

    now = datetime(2026, 7, 29, 9, 0)
    reminders.check_and_send_reminders(db, now)
    assert reminders.check_and_send_reminders(db, now) == []


def test_no_reminder_when_time_does_not_match(db_session_factory, monkeypatch):
    from app import reminders
    db, _ = _make_supp(db_session_factory)
    monkeypatch.setattr(reminders, "send_push", lambda db, payload: True)

    now = datetime(2026, 7, 29, 10, 0)
    assert reminders.check_and_send_reminders(db, now) == []


def test_inactive_supplement_skipped(db_session_factory, monkeypatch):
    from app import reminders
    from app.models import Supplement
    db, _ = _make_supp(db_session_factory)
    db.query(Supplement).one().active = False
    db.commit()
    monkeypatch.setattr(reminders, "send_push", lambda db, payload: True)

    now = datetime(2026, 7, 29, 9, 0)
    assert reminders.check_and_send_reminders(db, now) == []


def test_records_log_even_when_push_fails(db_session_factory, monkeypatch):
    from app import reminders
    db, schedule_id = _make_supp(db_session_factory)
    monkeypatch.setattr(reminders, "send_push", lambda db, payload: False)

    now = datetime(2026, 7, 29, 9, 0)
    assert reminders.check_and_send_reminders(db, now) == [schedule_id]
```

- [ ] **Step 3: Run tests, verify fail**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/test_reminders.py -v
```
Expected: FAIL — `ModuleNotFoundError: app.reminders`.

- [ ] **Step 4: Implement reminders module**

`backend/app/reminders.py`:
```python
import logging
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from .models import ReminderLog, Supplement
from .push import send_push

logger = logging.getLogger(__name__)


def check_and_send_reminders(db: Session, now: datetime) -> list[int]:
    """Send one push per due, not-yet-sent supplement schedule slot this
    minute. Returns the schedule_ids processed (sent or attempted)."""
    dow = str(now.weekday())  # 0=Mon … 6=Sun, matches days_of_week convention
    hhmm = now.strftime("%H:%M")
    today = now.date()

    supps = (db.query(Supplement).filter(Supplement.active.is_(True))
             .options(joinedload(Supplement.schedules)).all())
    processed: list[int] = []
    for supp in supps:
        for sched in supp.schedules:
            if dow not in sched.days_of_week or sched.time_of_day != hhmm:
                continue
            already = (db.query(ReminderLog)
                      .filter_by(schedule_id=sched.id, date=today).first())
            if already:
                continue
            send_push(db, {
                "title": "복용 알림",
                "body": f"{supp.product_name} 드실 시간이에요",
            })
            # Recorded whether push succeeded or not — one attempt per slot
            # per day; a dead subscription is covered by the dashboard's
            # existing pending-intake checklist (spec §6), not by retrying
            # every minute.
            db.add(ReminderLog(schedule_id=sched.id, date=today, sent_at=now))
            db.commit()
            processed.append(sched.id)
    return processed
```

- [ ] **Step 5: Wire APScheduler into main.py lifespan**

In `backend/app/main.py`, change:
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    from .db import SessionLocal
    from .seed import seed_evidence_and_limits, seed_metric_definitions
    db = SessionLocal()
    try:
        seed_metric_definitions(db)
        seed_evidence_and_limits(db)
    finally:
        db.close()

    yield
```
to:
```python
from contextlib import asynccontextmanager
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from .config import settings
from .db import init_db

scheduler = BackgroundScheduler()


def _reminder_tick() -> None:
    from .db import SessionLocal
    from .reminders import check_and_send_reminders
    db = SessionLocal()
    try:
        check_and_send_reminders(db, datetime.now())
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    from .db import SessionLocal
    from .seed import seed_evidence_and_limits, seed_metric_definitions
    db = SessionLocal()
    try:
        seed_metric_definitions(db)
        seed_evidence_and_limits(db)
    finally:
        db.close()

    scheduler.add_job(_reminder_tick, "interval", minutes=1, id="reminder_tick",
                      replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
```
Note: a plain `TestClient(app)` (no `with`) never runs `lifespan` (see `conftest.py` comment), so the scheduler never starts during the test suite — no interference with other tests.

- [ ] **Step 6: Run tests, verify pass**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add -A
git commit -m "feat: send supplement reminders via web push on a per-minute schedule"
```

---

### Task 6: Shared frontend photo-upload component

**Files:**
- Modify: `frontend/src/api.ts` (add `apiUpload`)
- Create: `frontend/src/PhotoUpload.tsx`

**Interfaces:**
- Produces: `apiUpload<T>(path, kind, file) -> Promise<T>`; `PhotoUploadButton<T>({kind, label, onExtracted})` React component; `photoUrl(path: string) -> string`.

- [ ] **Step 1: Add apiUpload to api.ts**

In `frontend/src/api.ts`, after the existing `api` function, add:
```typescript
export async function apiUpload<T>(path: string, kind: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("kind", kind);
  form.append("file", file);
  const res = await fetch(path, { method: "POST", credentials: "same-origin", body: form });
  if (res.status === 401 && !location.pathname.startsWith("/login")) {
    location.href = "/login";
    throw new Error("unauthorized");
  }
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

- [ ] **Step 2: Create PhotoUpload.tsx**

`frontend/src/PhotoUpload.tsx`:
```tsx
import { useRef, useState } from "react";
import { apiUpload } from "./api";

export interface ExtractResult<T> {
  photo_path: string;
  extracted: T | null;
  error: string | null;
}

export function PhotoUploadButton<T>({ kind, label, onExtracted }: {
  kind: string;
  label: string;
  onExtracted: (result: ExtractResult<T>) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const inputId = `photo-${kind}-${label}`;

  async function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const result = await apiUpload<ExtractResult<T>>("/api/photos/extract", kind, file);
      onExtracted(result);
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <>
      <input ref={inputRef} type="file" accept="image/*" capture="environment"
             onChange={onChange} className="hidden" id={inputId} />
      <label htmlFor={inputId}
             className="inline-block cursor-pointer rounded-full border border-teal-600 px-4 py-2 text-sm font-medium text-teal-700 transition-colors active:bg-teal-50">
        {loading ? "분석 중…" : `📷 ${label}`}
      </label>
    </>
  );
}

export function photoUrl(path: string): string {
  return `/api/photos/${path}`;
}
```

- [ ] **Step 3: Verify frontend builds**

```powershell
cd frontend; npm run build
```
Expected: no errors.

- [ ] **Step 4: Commit**

```powershell
git add -A
git commit -m "feat: add shared photo-upload component and multipart upload helper"
```

---

### Task 7: Wire meal + nutrition-label photos into CalendarPage

**Files:**
- Modify: `frontend/src/pages/CalendarPage.tsx`

**Interfaces:**
- Consumes: `PhotoUploadButton`, `photoUrl` from `../PhotoUpload`.
- Produces: `AddMealForm` now captures `photo_path` and per-item `nutrients`, sent through to `POST /api/meals` unchanged from Task 2's shape; `MealOut` gains `photo_path`, rendered as a thumbnail on logged meals.

- [ ] **Step 1: Add import and extend MealOut interface**

In `frontend/src/pages/CalendarPage.tsx`, change:
```typescript
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";

interface MealItemOut { id: number; name: string; amount: string; nutrient_source: string; }
interface MealOut { id: number; eaten_at: string; dish_name: string; items: MealItemOut[]; }
```
to:
```typescript
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { PhotoUploadButton, photoUrl } from "../PhotoUpload";

interface MealItemOut { id: number; name: string; amount: string; nutrient_source: string; }
interface MealOut {
  id: number; eaten_at: string; dish_name: string;
  photo_path: string | null; items: MealItemOut[];
}
interface MealExtract { dish_name?: string; items?: { name: string; amount: string }[]; }
interface LabelExtract {
  name?: string; amount?: string; nutrients?: Record<string, number | null>;
}
```

- [ ] **Step 2: Rewrite AddMealForm with photo wiring**

Replace the whole `AddMealForm` function with:
```tsx
function AddMealForm({ date, onDone }: { date: string; onDone: () => void }) {
  const [dish, setDish] = useState("");
  const [time, setTime] = useState("12:00");
  const [items, setItems] = useState<
    { name: string; amount: string; nutrients?: Record<string, number | null> }[]
  >([{ name: "", amount: "" }]);
  const [photoPath, setPhotoPath] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function applyMealExtract(result: {
    photo_path: string; extracted: MealExtract | null; error: string | null;
  }) {
    setPhotoPath(result.photo_path);
    if (result.extracted) {
      if (result.extracted.dish_name) setDish(result.extracted.dish_name);
      if (result.extracted.items?.length) setItems(result.extracted.items);
    }
    setNotice(result.error ? `사진은 저장했지만 자동 인식은 실패했어요: ${result.error}` : null);
  }

  function applyLabelExtract(result: {
    extracted: LabelExtract | null; error: string | null;
  }) {
    if (result.extracted) {
      setItems([...items.filter((i) => i.name.trim()), {
        name: result.extracted.name || "", amount: result.extracted.amount || "",
        nutrients: result.extracted.nutrients,
      }]);
    }
    setNotice(result.error ? `영양정보표 인식 실패: ${result.error}` : null);
  }

  async function save() {
    setSaving(true);
    try {
      await api("/api/meals", {
        method: "POST",
        body: JSON.stringify({
          eaten_at: `${date}T${time}:00`,
          dish_name: dish,
          photo_path: photoPath,
          items: items.filter((i) => i.name.trim()),
        }),
      });
      onDone();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3 rounded-2xl border border-stone-200/80 bg-white p-4 shadow-sm shadow-slate-200/50">
      <div className="flex gap-2">
        <PhotoUploadButton kind="meal" label="음식 사진" onExtracted={applyMealExtract} />
        <PhotoUploadButton kind="nutrition_label" label="영양정보표" onExtracted={applyLabelExtract} />
      </div>
      {notice && <p className="text-xs text-amber-600">{notice}</p>}
      {photoPath && (
        <img src={photoUrl(photoPath)} className="h-24 w-24 rounded-lg object-cover" />
      )}
      <div className="flex gap-2">
        <input value={dish} onChange={(e) => setDish(e.target.value)}
               placeholder="음식 이름 (예: 김치찌개)"
               className="flex-1 rounded-lg border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none" />
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)}
               className="rounded-lg border border-slate-300 px-2" />
      </div>
      {items.map((it, idx) => (
        <div key={idx} className="flex gap-2">
          <input value={it.name} placeholder="재료"
                 onChange={(e) => setItems(items.map((x, i) => i === idx ? { ...x, name: e.target.value } : x))}
                 className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-slate-900 focus:outline-none" />
          <input value={it.amount} placeholder="양 (예: 100g, 반 모)"
                 onChange={(e) => setItems(items.map((x, i) => i === idx ? { ...x, amount: e.target.value } : x))}
                 className="w-32 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-slate-900 focus:outline-none" />
        </div>
      ))}
      <div className="flex gap-2">
        <button onClick={() => setItems([...items, { name: "", amount: "" }])}
                className="py-2 text-sm font-medium text-teal-700">+ 재료 추가</button>
        <button onClick={save} disabled={saving || !dish.trim()}
                className="ml-auto rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:opacity-40">
          {saving ? "영양성분 계산 중…" : "저장"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Show meal photo thumbnail in DayDetail**

In `frontend/src/pages/CalendarPage.tsx`, inside `DayDetail`, change:
```tsx
            {m.items.length > 0 && (
              <p className="mt-1 text-xs text-slate-500">
                {m.items.map((i) => `${i.name}${i.nutrient_source === "ai_estimate" ? "*" : ""}`).join(", ")}
              </p>
            )}
```
to:
```tsx
            {m.items.length > 0 && (
              <p className="mt-1 text-xs text-slate-500">
                {m.items.map((i) => `${i.name}${i.nutrient_source === "ai_estimate" ? "*" : ""}`).join(", ")}
              </p>
            )}
            {m.photo_path && (
              <img src={photoUrl(m.photo_path)} className="mt-2 h-16 w-16 rounded-lg object-cover" />
            )}
```

- [ ] **Step 4: Manual QA checklist**

```powershell
cd backend; .venv\Scripts\uvicorn app.main:app --reload --port 8000
```
```powershell
cd frontend; npm run dev
```
- Open 캘린더 → 일 view → + 식사 기록.
- Tap "📷 음식 사진", pick an image → dish name/items prefill (or notice shows if extraction failed), thumbnail appears.
- Tap "📷 영양정보표" → a new item row appears with prefilled name/amount.
- Save → meal card shows the photo thumbnail.

- [ ] **Step 5: Verify frontend builds**

```powershell
cd frontend; npm run build
```

- [ ] **Step 6: Commit**

```powershell
git add -A
git commit -m "feat: capture meal and nutrition-label photos in the calendar meal form"
```

---

### Task 8: Wire supplement-label and lab-result photos into Supplements/MyData pages

**Files:**
- Modify: `frontend/src/pages/SupplementsPage.tsx`
- Modify: `frontend/src/pages/MyDataPage.tsx`

**Interfaces:**
- Consumes: `PhotoUploadButton`, `photoUrl` from `../PhotoUpload`.
- Produces: `Supp`/`emptyForm` gain `photo_path`; new `LabResultUpload` component in `MyDataPage.tsx` posting to `POST /api/metrics/entries/bulk` (Task 2).

- [ ] **Step 1: Extend Supp interface and emptyForm**

In `frontend/src/pages/SupplementsPage.tsx`, change:
```typescript
import { useEffect, useState } from "react";
import { api } from "../api";

interface Ingredient { ingredient_code: string; amount: number; unit: string; }
interface Schedule { id?: number; days_of_week: string; time_of_day: string; servings: number; }
interface Supp {
  id: number; brand: string; product_name: string; serving_size: string;
  ingredients: Ingredient[]; schedules: Schedule[];
}
```
to:
```typescript
import { useEffect, useState } from "react";
import { api } from "../api";
import { PhotoUploadButton, photoUrl } from "../PhotoUpload";

interface Ingredient { ingredient_code: string; amount: number; unit: string; }
interface Schedule { id?: number; days_of_week: string; time_of_day: string; servings: number; }
interface Supp {
  id: number; brand: string; product_name: string; serving_size: string;
  photo_path: string | null;
  ingredients: Ingredient[]; schedules: Schedule[];
}
interface LabelExtract {
  brand?: string; product_name?: string; serving_size?: string;
  ingredients?: Ingredient[];
}
```
and change:
```typescript
const emptyForm = () => ({
  brand: "", product_name: "", serving_size: "1정",
  ingredients: [{ ingredient_code: "", amount: 0, unit: "mg" }] as Ingredient[],
  schedules: [{ days_of_week: "0123456", time_of_day: "09:00", servings: 1 }] as Schedule[],
});
```
to:
```typescript
const emptyForm = () => ({
  brand: "", product_name: "", serving_size: "1정",
  photo_path: null as string | null,
  ingredients: [{ ingredient_code: "", amount: 0, unit: "mg" }] as Ingredient[],
  schedules: [{ days_of_week: "0123456", time_of_day: "09:00", servings: 1 }] as Schedule[],
});
```

- [ ] **Step 2: Add photo upload to SuppForm**

In `frontend/src/pages/SupplementsPage.tsx`, inside `SuppForm`, right after the `const [saving, setSaving] = useState(false);` line, add:
```tsx
  function applyExtract(result: {
    photo_path: string; extracted: LabelExtract | null; error: string | null;
  }) {
    setForm((f) => ({
      ...f,
      photo_path: result.photo_path,
      brand: result.extracted?.brand ?? f.brand,
      product_name: result.extracted?.product_name ?? f.product_name,
      serving_size: result.extracted?.serving_size ?? f.serving_size,
      ingredients: result.extracted?.ingredients?.length
        ? result.extracted.ingredients
        : f.ingredients,
    }));
  }
```
Then, right before the existing `<div className="flex gap-2">` that holds the brand/product_name/serving_size inputs, add:
```tsx
      <div className="flex items-center gap-2">
        <PhotoUploadButton kind="supplement_label" label="라벨 사진" onExtracted={applyExtract} />
        {form.photo_path && (
          <img src={photoUrl(form.photo_path)} className="h-12 w-12 rounded-lg object-cover" />
        )}
      </div>
```

- [ ] **Step 3: Show thumbnail on supplement list card**

In `frontend/src/pages/SupplementsPage.tsx`, inside the `supps.map(...)` card render, change:
```tsx
          <div className="flex items-start">
            <div>
              <p className="font-display text-lg font-bold text-slate-900">{s.product_name}</p>
              <p className="text-xs text-slate-500">{s.brand} · {s.serving_size}</p>
            </div>
```
to:
```tsx
          <div className="flex items-start gap-3">
            {s.photo_path && (
              <img src={photoUrl(s.photo_path)} className="h-12 w-12 rounded-lg object-cover" />
            )}
            <div>
              <p className="font-display text-lg font-bold text-slate-900">{s.product_name}</p>
              <p className="text-xs text-slate-500">{s.brand} · {s.serving_size}</p>
            </div>
```

- [ ] **Step 4: Add LabResultUpload to MyDataPage**

In `frontend/src/pages/MyDataPage.tsx`, change the import line:
```typescript
import { api } from "../api";
```
to:
```typescript
import { api } from "../api";
import { PhotoUploadButton } from "../PhotoUpload";
```
Then, after the `ProfileCard` function and before `export default function MyDataPage()`, add:
```tsx
interface LabEntry { metric_code: string; value_num: number | null; measured_at: string | null; }
interface LabExtract { entries?: LabEntry[]; }

function LabResultUpload({ defs, onSaved }: { defs: MetricDef[]; onSaved: () => void }) {
  const [entries, setEntries] = useState<LabEntry[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const defByCode = Object.fromEntries(defs.map((d) => [d.code, d]));

  function applyExtract(result: { extracted: LabExtract | null; error: string | null }) {
    setEntries((result.extracted?.entries ?? []).filter((e) => defByCode[e.metric_code]));
    setNotice(result.error ? `인식 실패: ${result.error}` : null);
  }

  async function save() {
    if (!entries?.length) return;
    setSaving(true);
    try {
      await api("/api/metrics/entries/bulk", {
        method: "POST",
        body: JSON.stringify({ entries }),
      });
      setEntries(null);
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="reveal space-y-3 rounded-2xl border border-stone-200/80 bg-white p-5 shadow-sm shadow-slate-200/50">
      <h2 className="font-display text-base font-bold text-slate-800">건강검진 결과지</h2>
      <PhotoUploadButton kind="lab_result" label="결과지 사진으로 입력" onExtracted={applyExtract} />
      {notice && <p className="text-xs text-amber-600">{notice}</p>}
      {entries && (
        <div className="space-y-2">
          {entries.map((e, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <span className="w-28 shrink-0 text-sm text-slate-700">
                {defByCode[e.metric_code]?.name_ko ?? e.metric_code}
              </span>
              <input type="number" value={e.value_num ?? ""}
                     onChange={(ev) => setEntries(entries.map((x, i) =>
                       i === idx ? { ...x, value_num: Number(ev.target.value) } : x))}
                     className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              <button onClick={() => setEntries(entries.filter((_, i) => i !== idx))}
                      className="text-xs text-slate-400">✕</button>
            </div>
          ))}
          <button onClick={save} disabled={saving || entries.length === 0}
                  className="w-full rounded-full bg-slate-900 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:opacity-40">
            {saving ? "저장 중…" : `${entries.length}개 항목 저장`}
          </button>
        </div>
      )}
    </section>
  );
}
```
Then in the `MyDataPage` function's returned JSX, change:
```tsx
      <ProfileCard />
      {DOMAIN_ORDER.map((domain) => (
```
to:
```tsx
      <ProfileCard />
      <LabResultUpload defs={defs} onSaved={reload} />
      {DOMAIN_ORDER.map((domain) => (
```

- [ ] **Step 5: Manual QA checklist**

```powershell
cd backend; .venv\Scripts\uvicorn app.main:app --reload --port 8000
```
```powershell
cd frontend; npm run dev
```
- 영양제 → + 추가 → "📷 라벨 사진" → fields prefill, thumbnail shows.
- 내 데이터 → "건강검진 결과지" section → upload → editable rows appear → 저장 → values show up under the matching domain rows.

- [ ] **Step 6: Verify frontend builds**

```powershell
cd frontend; npm run build
```

- [ ] **Step 7: Commit**

```powershell
git add -A
git commit -m "feat: capture supplement-label and lab-result photos in supplements/my-data pages"
```

---

### Task 9: Chat page

**Files:**
- Create: `frontend/src/pages/ChatPage.tsx`
- Modify: `frontend/src/App.tsx` (add tab + route)

**Interfaces:**
- Consumes: `GET/POST /api/chat/messages` (Task 3), `POST /api/metrics/entries` (existing).

- [ ] **Step 1: Create ChatPage.tsx**

`frontend/src/pages/ChatPage.tsx`:
```tsx
import { useEffect, useRef, useState } from "react";
import { api } from "../api";

interface ProposedEntry { metric_code: string; value_num: number | null; value_text: string | null; }
interface ChatMsg {
  id: number; role: "user" | "assistant"; content: string;
  proposed_entries: ProposedEntry[]; created_at: string;
}

function ProposedEntryCard({ entry, onConfirmed }: {
  entry: ProposedEntry; onConfirmed: () => void;
}) {
  const [saved, setSaved] = useState(false);
  async function confirm() {
    await api("/api/metrics/entries", { method: "POST", body: JSON.stringify(entry) });
    setSaved(true);
    onConfirmed();
  }
  return (
    <div className="mt-2 flex items-center gap-2 rounded-xl border border-teal-200 bg-teal-50 px-3 py-2 text-sm">
      <span className="text-teal-800">
        {entry.metric_code} = {entry.value_num ?? entry.value_text}
      </span>
      <button onClick={confirm} disabled={saved}
              className="ml-auto rounded-full bg-teal-700 px-3 py-1 text-xs font-medium text-white disabled:opacity-40">
        {saved ? "저장됨 ✓" : "저장"}
      </button>
    </div>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  function reload() {
    api<ChatMsg[]>("/api/chat/messages").then(setMessages);
  }
  useEffect(reload, []);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send() {
    if (!input.trim() || sending) return;
    setSending(true);
    const content = input;
    setInput("");
    try {
      const res = await api<{ user_message: ChatMsg; assistant_message: ChatMsg }>(
        "/api/chat/messages", { method: "POST", body: JSON.stringify({ content }) });
      setMessages((m) => [...m, res.user_message, res.assistant_message]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-80px)] max-w-lg flex-col px-4 pt-6">
      <header className="pb-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-teal-700/60">Chat</p>
        <h1 className="mt-1 font-display text-3xl font-extrabold leading-none text-slate-900">AI 채팅</h1>
      </header>
      <div className="flex-1 space-y-3 overflow-y-auto pb-3">
        {messages.length === 0 && (
          <p className="pt-8 text-center text-sm text-slate-400">
            건강 데이터에 대해 무엇이든 물어보세요.
          </p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
              m.role === "user" ? "bg-slate-900 text-white" : "border border-stone-200 bg-white text-slate-800"
            }`}>
              <p>{m.content}</p>
              {m.proposed_entries.map((e, i) => (
                <ProposedEntryCard key={i} entry={e} onConfirmed={reload} />
              ))}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="flex gap-2 border-t border-stone-200 py-3">
        <input value={input} onChange={(e) => setInput(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && send()}
               placeholder="메시지를 입력하세요"
               className="flex-1 rounded-full border border-slate-300 px-4 py-2.5 text-sm focus:border-slate-900 focus:outline-none" />
        <button onClick={send} disabled={sending || !input.trim()}
                className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:opacity-40">
          전송
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire tab and route into App.tsx**

In `frontend/src/App.tsx`, change:
```tsx
import { BrowserRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import MyDataPage from "./pages/MyDataPage";
import CalendarPage from "./pages/CalendarPage";
import SupplementsPage from "./pages/SupplementsPage";
import ReportPage from "./pages/ReportPage";
import DashboardPage from "./pages/DashboardPage";

const TABS = [
  { to: "/dashboard", label: "대시보드", icon: "🏠" },
  { to: "/data", label: "내 데이터", icon: "📊" },
  { to: "/calendar", label: "캘린더", icon: "📅" },
  { to: "/supplements", label: "영양제", icon: "💊" },
  { to: "/report", label: "리포트", icon: "📄" },
];
```
to:
```tsx
import { BrowserRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import MyDataPage from "./pages/MyDataPage";
import CalendarPage from "./pages/CalendarPage";
import SupplementsPage from "./pages/SupplementsPage";
import ReportPage from "./pages/ReportPage";
import DashboardPage from "./pages/DashboardPage";
import ChatPage from "./pages/ChatPage";

const TABS = [
  { to: "/dashboard", label: "대시보드", icon: "🏠" },
  { to: "/data", label: "내 데이터", icon: "📊" },
  { to: "/calendar", label: "캘린더", icon: "📅" },
  { to: "/supplements", label: "영양제", icon: "💊" },
  { to: "/chat", label: "채팅", icon: "💬" },
  { to: "/report", label: "리포트", icon: "📄" },
];
```
and change:
```tsx
          <Route path="/supplements" element={<SupplementsPage />} />
          <Route path="/report" element={<ReportPage />} />
```
to:
```tsx
          <Route path="/supplements" element={<SupplementsPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/report" element={<ReportPage />} />
```

- [ ] **Step 3: Manual QA checklist**

```powershell
cd backend; .venv\Scripts\uvicorn app.main:app --reload --port 8000
```
```powershell
cd frontend; npm run dev
```
- Open 채팅 tab, send a message → assistant reply appears.
- Send a message with a metric value (e.g. "몸무게 72kg") → if the assistant proposes a save, tap 저장 → check 내 데이터 shows the new value.

- [ ] **Step 4: Verify frontend builds**

```powershell
cd frontend; npm run build
```

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: add AI chat page with structured-save confirmations"
```

---

### Task 10: Push service worker + subscription UI

**Files:**
- Create: `frontend/public/sw.js`
- Create: `frontend/src/push.ts`
- Modify: `frontend/src/pages/DashboardPage.tsx` (notification card)

**Interfaces:**
- Produces: `pushSupported()`, `getPushSubscription()`, `enablePush()`, `disablePush()` in `push.ts`; a `PushCard` component rendered near the top of `DashboardPage`.

- [ ] **Step 1: Create the service worker**

`frontend/public/sw.js`:
```js
self.addEventListener("push", (event) => {
  let data = { title: "MyHub", body: "" };
  try { data = event.data.json(); } catch { /* malformed payload — show default */ }
  event.waitUntil(self.registration.showNotification(data.title, { body: data.body, data }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow("/dashboard"));
});
```

- [ ] **Step 2: Create push.ts**

`frontend/src/push.ts`:
```typescript
import { api } from "./api";

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const base64Safe = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64Safe);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export function pushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window;
}

export async function getPushSubscription(): Promise<PushSubscription | null> {
  if (!pushSupported()) return null;
  const reg = await navigator.serviceWorker.getRegistration();
  return reg ? reg.pushManager.getSubscription() : null;
}

export async function enablePush(): Promise<void> {
  if (!pushSupported()) throw new Error("이 브라우저는 알림을 지원하지 않아요");
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("알림 권한이 거부되었어요");

  const reg = await navigator.serviceWorker.register("/sw.js");
  const { key } = await api<{ key: string }>("/api/push/vapid-public-key");
  const subscription = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(key),
  });
  await api("/api/push/subscribe", {
    method: "POST",
    body: JSON.stringify({ subscription: subscription.toJSON() }),
  });
}

export async function disablePush(): Promise<void> {
  const subscription = await getPushSubscription();
  if (subscription) await subscription.unsubscribe();
  await api("/api/push/subscribe", { method: "DELETE" });
}
```

- [ ] **Step 3: Add PushCard to DashboardPage**

In `frontend/src/pages/DashboardPage.tsx`, change the import line:
```tsx
import { useEffect, useState } from "react";
import { api } from "../api";
import { Top3Card, type AnalysisDetail } from "./ReportPage";
```
to:
```tsx
import { useEffect, useState } from "react";
import { api } from "../api";
import { Top3Card, type AnalysisDetail } from "./ReportPage";
import { disablePush, enablePush, getPushSubscription } from "../push";
```
Then, right before `export default function DashboardPage() {`, add:
```tsx
function PushCard() {
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPushSubscription().then((s) => setEnabled(!!s));
  }, []);

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      if (enabled) { await disablePush(); setEnabled(false); }
      else { await enablePush(); setEnabled(true); }
    } catch (e) {
      setError(e instanceof Error ? e.message : "오류가 발생했어요");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex flex-wrap items-center gap-3 rounded-2xl border border-stone-200/80 bg-white p-3.5 shadow-sm shadow-slate-200/50">
      <span className="text-lg">🔔</span>
      <span className="text-sm text-slate-700">복용 알림</span>
      <button onClick={toggle} disabled={busy}
              className={`ml-auto rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                enabled ? "bg-emerald-500 text-white" : "border border-slate-300 text-slate-600"
              }`}>
        {busy ? "처리 중…" : enabled ? "켜짐" : "꺼짐"}
      </button>
      {error && <p className="w-full text-xs text-rose-600">{error}</p>}
    </section>
  );
}
```
Then, in the returned JSX, change:
```tsx
      <header>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-teal-700/60">Today</p>
        <h1 className="mt-1 font-display text-3xl font-extrabold leading-none text-slate-900">대시보드</h1>
      </header>

      {warnings.length > 0 && (
```
to:
```tsx
      <header>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-teal-700/60">Today</p>
        <h1 className="mt-1 font-display text-3xl font-extrabold leading-none text-slate-900">대시보드</h1>
      </header>

      <PushCard />

      {warnings.length > 0 && (
```

- [ ] **Step 4: Manual QA checklist**

```powershell
cd backend; .venv\Scripts\uvicorn app.main:app --reload --port 8000
```
```powershell
cd frontend; npm run dev
```
- Open 대시보드 in a browser that supports push (Chrome/Edge desktop, or Android Chrome).
- Tap "꺼짐" → browser asks for notification permission → grant → card flips to "켜짐".
- Set a supplement schedule for the current minute (영양제 tab) → within a minute of the backend running (with `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY` set), a system notification should appear; tapping it opens 대시보드.
- Tap "켜짐" → confirm it flips back to "꺼짐" and no more notifications arrive.
- On iOS Safari without "홈 화면에 추가", confirm the card shows the "지원하지 않아요" error gracefully instead of crashing (Safari's PWA-only push restriction — the existing 오늘의 영양제 checklist remains the fallback per spec §6).

- [ ] **Step 5: Verify frontend builds**

```powershell
cd frontend; npm run build
```

- [ ] **Step 6: Commit**

```powershell
git add -A
git commit -m "feat: add push service worker and notification enable/disable UI"
```
