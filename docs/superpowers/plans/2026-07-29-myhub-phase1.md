# MyHub Phase 1 — Core Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A usable single-user health-logging web app: login, master metric list with history charts, meal + supplement logging on a month/week/day calendar, nutrient resolution (식약처 DB → GPT fallback), deployable as one Docker container.

**Architecture:** One FastAPI app (SQLite via SQLAlchemy) serving a JSON API under `/api`, plus the built React SPA as static files. React (Vite + TS + Tailwind v4) mobile-first frontend with bottom-tab navigation. No AI analysis yet (Phase 2), no photos/push (Phase 3).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, pydantic-settings, itsdangerous, httpx, openai, pytest · Node 22, Vite, React 18, TypeScript, Tailwind v4, react-router-dom, recharts, vitest.

**Spec:** `docs/superpowers/specs/2026-07-29-myhub-design.md` (Phase 1 = spec §8 tasks 1–5)

## Global Constraints

- Single user. No signup. Password from env `MYHUB_PASSWORD`; session = signed cookie (itsdangerous), 30-day max age.
- All `/api/*` routes except `/api/auth/login` and `/api/health` require the `require_auth` dependency.
- UI text in Korean. Data (food/supplement names) accepted in Korean and English.
- Mobile-first: bottom tab bar, touch targets ≥ 44px, max content width `max-w-lg mx-auto`.
- Theme "clean clinical": bg `slate-50`, cards white rounded-xl, accent `sky-600` (#0284c7), success `emerald-500`, text `slate-800`/muted `slate-500`.
- Datetimes stored naive local (Asia/Seoul), ISO strings over the wire. Single user, one timezone — no tz conversion anywhere.
- JSON payload columns stored as TEXT (SQLite), serialized with `json.dumps`/`json.loads`.
- Schema management: `Base.metadata.create_all` only. `# ponytail: no alembic — single user; additive schema changes via create_all, destructive ones by hand`
- Frontend testing: one vitest smoke test (App renders). Pages verified by manual QA checklists in their tasks. Backend: pytest TDD per task.
- Commit after every green test cycle. Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Dev runs on Windows PowerShell: backend `cd backend; .venv\Scripts\uvicorn app.main:app --reload --port 8000`, frontend `cd frontend; npm run dev` (Vite proxies `/api` → 8000).

## File Structure (end state)

```
backend/
  requirements.txt
  app/
    __init__.py
    main.py            # create_app(), lifespan (init_db + seed), static/SPA serving
    config.py          # Settings (env)
    db.py              # engine, SessionLocal, get_db, init_db, Base
    models.py          # all Phase-1 tables
    auth.py            # login router + require_auth dependency
    seed.py            # METRIC_DEFINITIONS + seed_metric_definitions()
    nutrition.py       # NUTRIENT_KEYS, resolve_nutrients (MFDS → GPT → none)
    routers/
      __init__.py
      metrics.py       # definitions, entries, latest
      meals.py         # meal CRUD
      supplements.py   # supplements, schedules, intake logs
      calendar.py      # expand_schedules + combined feed
  tests/
    conftest.py
    test_health.py
    test_models.py
    test_auth.py
    test_metrics.py
    test_meals.py
    test_supplements.py
    test_calendar.py
    test_nutrition.py
frontend/
  vite.config.ts, package.json, index.html, tsconfig…
  src/
    main.tsx, App.tsx, api.ts, index.css
    pages/LoginPage.tsx
    pages/MyDataPage.tsx
    pages/CalendarPage.tsx
    pages/SupplementsPage.tsx
    App.test.tsx
Dockerfile
.gitignore
```

---

### Task 1: Backend + frontend scaffold, health endpoint

**Files:**
- Create: `.gitignore`, `backend/requirements.txt`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/main.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`
- Create (generated): `frontend/` via Vite scaffold

**Interfaces:**
- Produces: `create_app() -> FastAPI` and module-level `app` in `app.main`; `settings` object (`myhub_password`, `myhub_secret_key`, `myhub_data_dir`, `myhub_static_dir`, `mfds_api_key`, `openai_api_key`, `openai_model_mini`); `Base`, `SessionLocal`, `get_db`, `init_db()` in `app.db`; pytest fixtures `db_session_factory`, `client`.

- [ ] **Step 1: Scaffold directories, venv, requirements**

```powershell
New-Item -ItemType Directory -Force backend\app, backend\tests
cd backend
python -m venv .venv
.venv\Scripts\pip install -U pip
```

`backend/requirements.txt`:
```
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0
pydantic-settings>=2.4
itsdangerous>=2.2
httpx>=0.27
openai>=1.50
pytest>=8.0
```

```powershell
.venv\Scripts\pip install -r requirements.txt
```

`.gitignore` (repo root):
```
.venv/
__pycache__/
*.pyc
data/
node_modules/
frontend/dist/
.env
```

- [ ] **Step 2: Write failing health test**

`backend/tests/test_health.py`:
```python
def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}
```

`backend/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app


@pytest.fixture()
def db_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401 — register tables (module exists from Task 2 on)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False)


@pytest.fixture()
def client(db_session_factory):
    app = create_app()

    def override_get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # plain TestClient (no `with`) does NOT run lifespan — no file DB side effects in tests
    return TestClient(app)
```

Note: until Task 2 exists, `import app.models` fails — for this task only, create an empty `backend/app/models.py` (`"""Models added in Task 2."""`).

- [ ] **Step 3: Run test, verify it fails**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/test_health.py -v
```
Expected: FAIL / collection error — `app.main` not found.

- [ ] **Step 4: Implement config, db, main**

`backend/app/__init__.py`: empty file.

`backend/app/config.py`:
```python
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    myhub_password: str = "changeme"
    myhub_secret_key: str = "dev-secret-change-in-prod"
    myhub_data_dir: Path = Path("data")
    myhub_static_dir: Path = Path("static")
    mfds_api_key: str = ""
    openai_api_key: str = ""
    openai_model_mini: str = "gpt-5-mini"

    @property
    def db_path(self) -> Path:
        return self.myhub_data_dir / "myhub.db"


settings = Settings()
```

`backend/app/db.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401 — register tables

    settings.myhub_data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
```

`backend/app/main.py`:
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="MyHub", lifespan=lifespan)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app


app = create_app()
```

- [ ] **Step 5: Run test, verify pass**

```powershell
.venv\Scripts\python -m pytest tests/ -v
```
Expected: 1 passed.

- [ ] **Step 6: Frontend scaffold**

```powershell
cd ..
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install react-router-dom recharts tailwindcss @tailwindcss/vite
npm install -D vitest jsdom @testing-library/react @testing-library/jest-dom
```

Replace `frontend/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
} as any);
```

Replace `frontend/src/index.css` with:
```css
@import "tailwindcss";
```

Add to `frontend/package.json` scripts: `"test": "vitest run"`.

- [ ] **Step 7: Verify frontend builds**

```powershell
npm run build
```
Expected: `dist/` produced, no errors.

- [ ] **Step 8: Commit**

```powershell
git add -A
git commit -m "feat: scaffold FastAPI backend and Vite React frontend with health endpoint"
```

---

### Task 2: Database models

**Files:**
- Modify: `backend/app/models.py` (replace placeholder)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `Base` from `app.db`.
- Produces (exact model/field names later tasks rely on):
  - `Profile(id, name, sex, birth_date, push_subscription)`
  - `MetricDefinition(code [pk str], name_ko, unit, domain, input_type, range_low, range_high)`
  - `MetricEntry(id, metric_code, value_num, value_text, measured_at, source)`
  - `Meal(id, eaten_at, dish_name, note, photo_path, items → MealItem)`
  - `MealItem(id, meal_id, name, amount, nutrients [JSON TEXT], nutrient_source)`
  - `Supplement(id, brand, product_name, serving_size, active, photo_path, ingredients, schedules)`
  - `SupplementIngredient(id, supplement_id, ingredient_code, amount, unit)`
  - `SupplementSchedule(id, supplement_id, days_of_week ["0"–"6" digits, 0=Mon], time_of_day "HH:MM", servings, supplement)`
  - `IntakeLog(id, schedule_id, date, status)` — unique `(schedule_id, date)`

- [ ] **Step 1: Write failing test**

`backend/tests/test_models.py`:
```python
from datetime import date, datetime


def test_models_roundtrip(db_session_factory):
    from app.models import (
        IntakeLog,
        Meal,
        MealItem,
        MetricDefinition,
        MetricEntry,
        Supplement,
        SupplementIngredient,
        SupplementSchedule,
    )

    db = db_session_factory()

    db.add(MetricDefinition(code="weight_kg", name_ko="몸무게", unit="kg",
                            domain="body", input_type="number",
                            range_low=30, range_high=200))
    db.add(MetricEntry(metric_code="weight_kg", value_num=72.5,
                       measured_at=datetime(2026, 7, 29, 8, 0)))

    meal = Meal(eaten_at=datetime(2026, 7, 29, 12, 0), dish_name="김치찌개")
    meal.items.append(MealItem(name="돼지고기", amount="100g"))
    db.add(meal)

    supp = Supplement(brand="나우푸드", product_name="오메가3", serving_size="1캡슐")
    supp.ingredients.append(SupplementIngredient(
        ingredient_code="omega3", amount=1000, unit="mg"))
    supp.schedules.append(SupplementSchedule(
        days_of_week="0123456", time_of_day="09:00", servings=1))
    db.add(supp)
    db.commit()

    db.add(IntakeLog(schedule_id=supp.schedules[0].id,
                     date=date(2026, 7, 29), status="taken"))
    db.commit()

    assert db.query(Meal).one().items[0].name == "돼지고기"
    assert db.query(Supplement).one().active is True
    assert db.query(SupplementSchedule).one().supplement.product_name == "오메가3"
    assert db.query(IntakeLog).one().status == "taken"
```

- [ ] **Step 2: Run test, verify fails**

```powershell
.venv\Scripts\python -m pytest tests/test_models.py -v
```
Expected: FAIL — `ImportError` (models don't exist).

- [ ] **Step 3: Implement models**

`backend/app/models.py`:
```python
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Profile(Base):
    __tablename__ = "profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    sex: Mapped[str | None] = mapped_column(String)          # "M" | "F"
    birth_date: Mapped[date | None] = mapped_column(Date)
    push_subscription: Mapped[str | None] = mapped_column(Text)  # JSON, Phase 3


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"
    code: Mapped[str] = mapped_column(String, primary_key=True)
    name_ko: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String, default="")
    domain: Mapped[str] = mapped_column(String)      # body | lab | lifestyle | symptom
    input_type: Mapped[str] = mapped_column(String)  # number | scale | text
    range_low: Mapped[float | None] = mapped_column(Float)
    range_high: Mapped[float | None] = mapped_column(Float)


class MetricEntry(Base):
    __tablename__ = "metric_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    metric_code: Mapped[str] = mapped_column(ForeignKey("metric_definitions.code"))
    value_num: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(Text)
    measured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    source: Mapped[str] = mapped_column(String, default="manual")  # manual | photo


class Meal(Base):
    __tablename__ = "meals"
    id: Mapped[int] = mapped_column(primary_key=True)
    eaten_at: Mapped[datetime] = mapped_column(DateTime)
    dish_name: Mapped[str] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(Text)
    photo_path: Mapped[str | None] = mapped_column(String)  # Phase 3
    items: Mapped[list["MealItem"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan")


class MealItem(Base):
    __tablename__ = "meal_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id"))
    name: Mapped[str] = mapped_column(String)
    amount: Mapped[str] = mapped_column(String, default="")  # free text: "100g", "1공기"
    nutrients: Mapped[str | None] = mapped_column(Text)      # JSON {kcal, protein_g, ...}
    nutrient_source: Mapped[str] = mapped_column(String, default="none")  # mfds_db | ai_estimate | none
    meal: Mapped["Meal"] = relationship(back_populates="items")


class Supplement(Base):
    __tablename__ = "supplements"
    id: Mapped[int] = mapped_column(primary_key=True)
    brand: Mapped[str] = mapped_column(String, default="")
    product_name: Mapped[str] = mapped_column(String)
    serving_size: Mapped[str] = mapped_column(String, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    photo_path: Mapped[str | None] = mapped_column(String)  # Phase 3
    ingredients: Mapped[list["SupplementIngredient"]] = relationship(
        back_populates="supplement", cascade="all, delete-orphan")
    schedules: Mapped[list["SupplementSchedule"]] = relationship(
        back_populates="supplement", cascade="all, delete-orphan")


class SupplementIngredient(Base):
    __tablename__ = "supplement_ingredients"
    id: Mapped[int] = mapped_column(primary_key=True)
    supplement_id: Mapped[int] = mapped_column(ForeignKey("supplements.id"))
    ingredient_code: Mapped[str] = mapped_column(String)  # snake_case, e.g. vitamin_d
    amount: Mapped[float] = mapped_column(Float)          # per serving
    unit: Mapped[str] = mapped_column(String)             # mg | ug | IU | g
    supplement: Mapped["Supplement"] = relationship(back_populates="ingredients")


class SupplementSchedule(Base):
    __tablename__ = "supplement_schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    supplement_id: Mapped[int] = mapped_column(ForeignKey("supplements.id"))
    days_of_week: Mapped[str] = mapped_column(String)  # digits, 0=Mon … 6=Sun, e.g. "024"
    time_of_day: Mapped[str] = mapped_column(String)   # "HH:MM"
    servings: Mapped[float] = mapped_column(Float, default=1)
    supplement: Mapped["Supplement"] = relationship(back_populates="schedules")


class IntakeLog(Base):
    __tablename__ = "intake_logs"
    __table_args__ = (UniqueConstraint("schedule_id", "date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("supplement_schedules.id"))
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String)  # taken | skipped
```

- [ ] **Step 4: Run tests, verify pass**

```powershell
.venv\Scripts\python -m pytest tests/ -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: add Phase 1 SQLAlchemy models"
```

---

### Task 3: Auth + profile (login, session cookie, route guard, profile setup)

**Files:**
- Create: `backend/app/auth.py`
- Modify: `backend/app/main.py` (include router), `backend/tests/conftest.py` (add `auth_client`)
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `settings` from `app.config`; `Profile` model.
- Produces: `require_auth` FastAPI dependency (raises 401); `POST /api/auth/login {password}` sets cookie `myhub_session`; `GET /api/auth/me` → `{"ok": true}` when logged in; `GET /api/profile` → `{name, sex, birth_date}` (nulls until set); `PUT /api/profile {name?, sex?, birth_date?}` upserts the single row; fixture `auth_client` (logged-in `TestClient`). All later routers attach `dependencies=[Depends(require_auth)]`. Phase 2 reads `sex`/`birth_date` for KDRI lookups.

- [ ] **Step 1: Write failing tests**

`backend/tests/test_auth.py`:
```python
def test_login_wrong_password(client):
    res = client.post("/api/auth/login", json={"password": "nope"})
    assert res.status_code == 401


def test_login_and_me(client):
    assert client.get("/api/auth/me").status_code == 401
    res = client.post("/api/auth/login", json={"password": "changeme"})
    assert res.status_code == 200
    assert "myhub_session" in client.cookies
    assert client.get("/api/auth/me").status_code == 200


def test_profile_upsert(auth_client):
    assert auth_client.get("/api/profile").json() == {
        "name": "", "sex": None, "birth_date": None}
    res = auth_client.put("/api/profile", json={
        "name": "길섭", "sex": "M", "birth_date": "1990-06-25"})
    assert res.status_code == 200
    assert auth_client.get("/api/profile").json() == {
        "name": "길섭", "sex": "M", "birth_date": "1990-06-25"}
```

Append to `backend/tests/conftest.py`:
```python
@pytest.fixture()
def auth_client(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "myhub_password", "changeme")
    res = client.post("/api/auth/login", json={"password": "changeme"})
    assert res.status_code == 200
    return client
```
Also add `monkeypatch.setattr(settings, "myhub_password", "changeme")`-style safety to `test_login_and_me` if your local env sets `MYHUB_PASSWORD`: put `from app.config import settings` + `monkeypatch.setattr(settings, "myhub_password", "changeme")` at the top of both tests (add `monkeypatch` parameter).

- [ ] **Step 2: Run tests, verify fail**

```powershell
.venv\Scripts\python -m pytest tests/test_auth.py -v
```
Expected: FAIL — 404 on `/api/auth/login`.

- [ ] **Step 3: Implement auth**

`backend/app/auth.py`:
```python
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
                        httponly=True, samesite="lax")
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
```

In `backend/app/main.py`, inside `create_app()` before the health route:
```python
    from . import auth
    app.include_router(auth.router)
    app.include_router(auth.profile_router)
```

Note: `secure=True` cookie flag is set in Task 13 (behind HTTPS in prod); local dev over http needs it off.

- [ ] **Step 4: Run tests, verify pass**

```powershell
.venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: add single-user session auth with signed cookie"
```

---

### Task 4: Metric definitions seed + metrics API

**Files:**
- Create: `backend/app/seed.py`, `backend/app/routers/__init__.py`, `backend/app/routers/metrics.py`
- Modify: `backend/app/main.py` (include router, seed in lifespan)
- Test: `backend/tests/test_metrics.py`

**Interfaces:**
- Consumes: models, `get_db`, `require_auth`, `auth_client` fixture.
- Produces:
  - `seed_metric_definitions(db) -> None` (idempotent; call with a Session)
  - `GET /api/metrics/definitions` → `[{code, name_ko, unit, domain, input_type, range_low, range_high}]`
  - `GET /api/metrics/latest` → `{code: {value_num, value_text, measured_at}}`
  - `GET /api/metrics/entries?code=X&limit=N` → newest-first entries
  - `POST /api/metrics/entries {metric_code, value_num?, value_text?, measured_at?}` → 201

- [ ] **Step 1: Write failing tests**

`backend/tests/test_metrics.py`:
```python
import pytest


@pytest.fixture()
def seeded_client(auth_client, db_session_factory):
    from app.seed import seed_metric_definitions
    db = db_session_factory()
    seed_metric_definitions(db)
    db.close()
    return auth_client


def test_definitions_seeded(seeded_client):
    res = seeded_client.get("/api/metrics/definitions")
    assert res.status_code == 200
    defs = res.json()
    codes = {d["code"] for d in defs}
    assert {"weight_kg", "bp_systolic", "vitamin_d", "sleep_hours", "fatigue"} <= codes
    assert all(d["domain"] in {"body", "lab", "lifestyle", "symptom"} for d in defs)


def test_requires_auth(client):
    assert client.get("/api/metrics/definitions").status_code == 401


def test_entry_roundtrip_and_latest(seeded_client):
    res = seeded_client.post("/api/metrics/entries", json={
        "metric_code": "weight_kg", "value_num": 72.5,
        "measured_at": "2026-07-28T08:00:00"})
    assert res.status_code == 201
    res = seeded_client.post("/api/metrics/entries", json={
        "metric_code": "weight_kg", "value_num": 72.0,
        "measured_at": "2026-07-29T08:00:00"})
    assert res.status_code == 201

    latest = seeded_client.get("/api/metrics/latest").json()
    assert latest["weight_kg"]["value_num"] == 72.0

    entries = seeded_client.get("/api/metrics/entries",
                                params={"code": "weight_kg"}).json()
    assert [e["value_num"] for e in entries] == [72.0, 72.5]  # newest first


def test_entry_validation(seeded_client):
    # unknown code
    assert seeded_client.post("/api/metrics/entries", json={
        "metric_code": "nope", "value_num": 1}).status_code == 404
    # number metric without value_num
    assert seeded_client.post("/api/metrics/entries", json={
        "metric_code": "weight_kg", "value_text": "hi"}).status_code == 422
    # scale out of range
    assert seeded_client.post("/api/metrics/entries", json={
        "metric_code": "fatigue", "value_num": 9}).status_code == 422
    # text metric works
    assert seeded_client.post("/api/metrics/entries", json={
        "metric_code": "medications", "value_text": "혈압약"}).status_code == 201
```

- [ ] **Step 2: Run tests, verify fail**

```powershell
.venv\Scripts\python -m pytest tests/test_metrics.py -v
```
Expected: FAIL — `app.seed` missing / 404s.

- [ ] **Step 3: Implement seed**

`backend/app/seed.py`:
```python
from sqlalchemy.orm import Session

from .models import MetricDefinition

# (code, name_ko, unit, domain, input_type, range_low, range_high)
# ranges = general adult reference ranges; None = no range. scale = 0 없음 / 1 가끔 / 2 자주 / 3 심함
METRIC_DEFINITIONS = [
    # 신체 기본
    ("height_cm",       "키",                "cm",    "body", "number", 100, 220),
    ("weight_kg",       "몸무게",            "kg",    "body", "number", 30, 200),
    ("body_fat_pct",    "체지방률",          "%",     "body", "number", 10, 25),
    ("waist_cm",        "허리둘레",          "cm",    "body", "number", None, 90),
    ("bp_systolic",     "수축기 혈압",       "mmHg",  "body", "number", 90, 120),
    ("bp_diastolic",    "이완기 혈압",       "mmHg",  "body", "number", 60, 80),
    ("heart_rate",      "안정시 심박수",     "bpm",   "body", "number", 60, 100),
    # 혈액검사
    ("fasting_glucose", "공복혈당",          "mg/dL", "lab", "number", 70, 100),
    ("hba1c",           "당화혈색소",        "%",     "lab", "number", 4.0, 5.6),
    ("total_chol",      "총콜레스테롤",      "mg/dL", "lab", "number", None, 200),
    ("ldl",             "LDL 콜레스테롤",    "mg/dL", "lab", "number", None, 130),
    ("hdl",             "HDL 콜레스테롤",    "mg/dL", "lab", "number", 40, None),
    ("triglycerides",   "중성지방",          "mg/dL", "lab", "number", None, 150),
    ("vitamin_d",       "비타민D (25-OH)",   "ng/mL", "lab", "number", 30, 100),
    ("ferritin",        "페리틴",            "ng/mL", "lab", "number", 24, 336),
    ("hemoglobin",      "혈색소",            "g/dL",  "lab", "number", 12, 17),
    ("ast",             "AST (GOT)",         "U/L",   "lab", "number", None, 40),
    ("alt",             "ALT (GPT)",         "U/L",   "lab", "number", None, 40),
    ("creatinine",      "크레아티닌",        "mg/dL", "lab", "number", 0.5, 1.2),
    ("tsh",             "갑상선자극호르몬",  "mIU/L", "lab", "number", 0.4, 4.0),
    # 생활습관
    ("sleep_hours",     "수면시간",          "시간",  "lifestyle", "number", 6, 9),
    ("exercise_min",    "운동시간",          "분/일", "lifestyle", "number", 30, None),
    ("water_ml",        "물 섭취량",         "mL",    "lifestyle", "number", 1500, 2500),
    ("caffeine_cups",   "카페인",            "잔",    "lifestyle", "number", None, 3),
    ("alcohol_drinks",  "음주",              "잔",    "lifestyle", "number", None, 2),
    ("smoking",         "흡연",              "개비",  "lifestyle", "number", None, 0),
    ("stress_level",    "스트레스",          "",      "lifestyle", "scale", 0, 3),
    # 증상
    ("fatigue",         "피로감",            "",      "symptom", "scale", 0, 3),
    ("hair_loss",       "탈모",              "",      "symptom", "scale", 0, 3),
    ("digestion_issue", "소화불량",          "",      "symptom", "scale", 0, 3),
    ("headache",        "두통",              "",      "symptom", "scale", 0, 3),
    ("skin_trouble",    "피부 트러블",       "",      "symptom", "scale", 0, 3),
    ("sleep_quality_low", "수면의 질 저하",  "",      "symptom", "scale", 0, 3),
    ("conditions",      "진단받은 질환",     "",      "symptom", "text", None, None),
    ("medications",     "복용 중인 약",      "",      "symptom", "text", None, None),
    ("allergies",       "알레르기",          "",      "symptom", "text", None, None),
]


def seed_metric_definitions(db: Session) -> None:
    existing = {code for (code,) in db.query(MetricDefinition.code).all()}
    for code, name_ko, unit, domain, input_type, lo, hi in METRIC_DEFINITIONS:
        if code not in existing:
            db.add(MetricDefinition(code=code, name_ko=name_ko, unit=unit,
                                    domain=domain, input_type=input_type,
                                    range_low=lo, range_high=hi))
    db.commit()
```

- [ ] **Step 4: Implement metrics router**

`backend/app/routers/__init__.py`: empty file.

`backend/app/routers/metrics.py`:
```python
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import require_auth
from ..db import get_db
from ..models import MetricDefinition, MetricEntry

router = APIRouter(prefix="/api/metrics", tags=["metrics"],
                   dependencies=[Depends(require_auth)])


@router.get("/definitions")
def list_definitions(db: Session = Depends(get_db)):
    defs = db.query(MetricDefinition).all()
    return [{"code": d.code, "name_ko": d.name_ko, "unit": d.unit,
             "domain": d.domain, "input_type": d.input_type,
             "range_low": d.range_low, "range_high": d.range_high}
            for d in defs]


@router.get("/latest")
def latest_per_metric(db: Session = Depends(get_db)):
    entries = (db.query(MetricEntry)
               .order_by(MetricEntry.measured_at.asc()).all())
    out: dict[str, dict] = {}
    for e in entries:  # ascending — last write per code wins
        out[e.metric_code] = {"value_num": e.value_num,
                              "value_text": e.value_text,
                              "measured_at": e.measured_at.isoformat()}
    return out


@router.get("/entries")
def list_entries(code: str, limit: int = 100, db: Session = Depends(get_db)):
    q = (db.query(MetricEntry).filter(MetricEntry.metric_code == code)
         .order_by(MetricEntry.measured_at.desc()).limit(limit))
    return [{"id": e.id, "metric_code": e.metric_code,
             "value_num": e.value_num, "value_text": e.value_text,
             "measured_at": e.measured_at.isoformat()} for e in q]


class EntryIn(BaseModel):
    metric_code: str
    value_num: float | None = None
    value_text: str | None = None
    measured_at: datetime | None = None


@router.post("/entries", status_code=201)
def create_entry(body: EntryIn, db: Session = Depends(get_db)):
    d = db.get(MetricDefinition, body.metric_code)
    if d is None:
        raise HTTPException(404, "알 수 없는 항목입니다")
    if d.input_type in ("number", "scale") and body.value_num is None:
        raise HTTPException(422, "숫자 값이 필요합니다")
    if d.input_type == "text" and not body.value_text:
        raise HTTPException(422, "텍스트 값이 필요합니다")
    if d.input_type == "scale" and body.value_num not in (0, 1, 2, 3):
        raise HTTPException(422, "0~3 값이어야 합니다")
    e = MetricEntry(metric_code=body.metric_code, value_num=body.value_num,
                    value_text=body.value_text,
                    measured_at=body.measured_at or datetime.now())
    db.add(e)
    db.commit()
    return {"id": e.id}
```

In `backend/app/main.py`: add router include inside `create_app()`:
```python
    from .routers import metrics
    app.include_router(metrics.router)
```
And in `lifespan`, after `init_db()`:
```python
    from .db import SessionLocal
    from .seed import seed_metric_definitions
    db = SessionLocal()
    try:
        seed_metric_definitions(db)
    finally:
        db.close()
```

- [ ] **Step 5: Run tests, verify pass**

```powershell
.venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add -A
git commit -m "feat: seed master metric catalog and add metrics API"
```

---

### Task 5: Meals API

**Files:**
- Create: `backend/app/routers/meals.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_meals.py`

**Interfaces:**
- Consumes: `Meal`, `MealItem`, `get_db`, `require_auth`.
- Produces:
  - `POST /api/meals {eaten_at, dish_name, note?, items: [{name, amount}]}` → 201 `{id}`
  - `GET /api/meals?start=YYYY-MM-DD&end=YYYY-MM-DD` → meals with items (incl. `nutrients` parsed JSON, `nutrient_source`)
  - `DELETE /api/meals/{id}` → 204
  - Meal item nutrients stay `None`/`"none"` here — Task 8 wires resolution into `create_meal` via `resolve_nutrients(name, amount)`.
  - Serializer `meal_to_dict(meal) -> dict` (used by calendar too — import from this module).

- [ ] **Step 1: Write failing tests**

`backend/tests/test_meals.py`:
```python
def test_meal_crud(auth_client):
    res = auth_client.post("/api/meals", json={
        "eaten_at": "2026-07-29T12:00:00",
        "dish_name": "김치찌개",
        "items": [{"name": "돼지고기", "amount": "100g"},
                  {"name": "두부", "amount": "반 모"}]})
    assert res.status_code == 201
    meal_id = res.json()["id"]

    res = auth_client.get("/api/meals",
                          params={"start": "2026-07-29", "end": "2026-07-29"})
    meals = res.json()
    assert len(meals) == 1
    assert meals[0]["dish_name"] == "김치찌개"
    assert [i["name"] for i in meals[0]["items"]] == ["돼지고기", "두부"]
    assert meals[0]["items"][0]["nutrient_source"] == "none"

    # outside range → empty
    assert auth_client.get("/api/meals",
                           params={"start": "2026-07-30", "end": "2026-07-31"}).json() == []

    assert auth_client.delete(f"/api/meals/{meal_id}").status_code == 204
    assert auth_client.get("/api/meals",
                           params={"start": "2026-07-29", "end": "2026-07-29"}).json() == []


def test_meals_require_auth(client):
    assert client.get("/api/meals",
                      params={"start": "2026-07-29", "end": "2026-07-29"}).status_code == 401
```

- [ ] **Step 2: Run tests, verify fail**

```powershell
.venv\Scripts\python -m pytest tests/test_meals.py -v
```
Expected: FAIL — 404.

- [ ] **Step 3: Implement meals router**

`backend/app/routers/meals.py`:
```python
import json
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import require_auth
from ..db import get_db
from ..models import Meal, MealItem

router = APIRouter(prefix="/api/meals", tags=["meals"],
                   dependencies=[Depends(require_auth)])


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
    for it in body.items:
        meal.items.append(MealItem(name=it.name, amount=it.amount))
    db.add(meal)
    db.commit()
    return {"id": meal.id}


@router.get("")
def list_meals(start: date, end: date, db: Session = Depends(get_db)):
    lo = datetime.combine(start, time.min)
    hi = datetime.combine(end + timedelta(days=1), time.min)
    meals = (db.query(Meal)
             .filter(Meal.eaten_at >= lo, Meal.eaten_at < hi)
             .order_by(Meal.eaten_at).all())
    return [meal_to_dict(m) for m in meals]


@router.delete("/{meal_id}", status_code=204)
def delete_meal(meal_id: int, db: Session = Depends(get_db)):
    meal = db.get(Meal, meal_id)
    if meal is None:
        raise HTTPException(404, "식사를 찾을 수 없습니다")
    db.delete(meal)
    db.commit()
```

In `create_app()`: `from .routers import meals` + `app.include_router(meals.router)` (extend the existing import line: `from .routers import meals, metrics`).

Note: no meal edit endpoint — edit = delete + re-log. `# ponytail: add PUT if editing proves annoying in daily use`

- [ ] **Step 4: Run tests, verify pass**

```powershell
.venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: add meals API with item logging"
```

---

### Task 6: Supplements + intake API

**Files:**
- Create: `backend/app/routers/supplements.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_supplements.py`

**Interfaces:**
- Consumes: `Supplement`, `SupplementIngredient`, `SupplementSchedule`, `IntakeLog`.
- Produces:
  - `GET /api/supplements` → active supplements with `ingredients` and `schedules` (each schedule has `id`)
  - `POST /api/supplements {brand, product_name, serving_size, ingredients: [{ingredient_code, amount, unit}], schedules: [{days_of_week, time_of_day, servings}]}` → 201 `{id}`
  - `PUT /api/supplements/{id}` same body → replaces ingredients/schedules wholesale
  - `DELETE /api/supplements/{id}` → 204, soft delete (`active=False`)
  - `POST /api/intake {schedule_id, date, status}` → upsert on `(schedule_id, date)`; `status` ∈ `taken|skipped`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_supplements.py`:
```python
SUPP = {
    "brand": "나우푸드", "product_name": "오메가3", "serving_size": "1캡슐",
    "ingredients": [{"ingredient_code": "omega3", "amount": 1000, "unit": "mg"}],
    "schedules": [{"days_of_week": "0123456", "time_of_day": "09:00", "servings": 1}],
}


def test_supplement_crud(auth_client):
    res = auth_client.post("/api/supplements", json=SUPP)
    assert res.status_code == 201
    sid = res.json()["id"]

    supps = auth_client.get("/api/supplements").json()
    assert len(supps) == 1
    assert supps[0]["ingredients"][0]["ingredient_code"] == "omega3"
    schedule_id = supps[0]["schedules"][0]["id"]

    # replace wholesale
    updated = dict(SUPP, product_name="오메가3 골드",
                   schedules=[{"days_of_week": "024", "time_of_day": "21:00",
                               "servings": 2}])
    assert auth_client.put(f"/api/supplements/{sid}", json=updated).status_code == 200
    supps = auth_client.get("/api/supplements").json()
    assert supps[0]["product_name"] == "오메가3 골드"
    assert supps[0]["schedules"][0]["time_of_day"] == "21:00"

    # intake upsert
    new_schedule_id = supps[0]["schedules"][0]["id"]
    for status in ("taken", "skipped"):
        res = auth_client.post("/api/intake", json={
            "schedule_id": new_schedule_id, "date": "2026-07-29",
            "status": status})
        assert res.status_code == 200

    # soft delete
    assert auth_client.delete(f"/api/supplements/{sid}").status_code == 204
    assert auth_client.get("/api/supplements").json() == []


def test_supplements_require_auth(client):
    assert client.get("/api/supplements").status_code == 401
```

- [ ] **Step 2: Run tests, verify fail**

```powershell
.venv\Scripts\python -m pytest tests/test_supplements.py -v
```
Expected: FAIL — 404.

- [ ] **Step 3: Implement supplements router**

`backend/app/routers/supplements.py`:
```python
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import require_auth
from ..db import get_db
from ..models import IntakeLog, Supplement, SupplementIngredient, SupplementSchedule

router = APIRouter(prefix="/api", tags=["supplements"],
                   dependencies=[Depends(require_auth)])


class IngredientIn(BaseModel):
    ingredient_code: str
    amount: float
    unit: str


class ScheduleIn(BaseModel):
    days_of_week: str   # digits 0=Mon … 6=Sun
    time_of_day: str    # "HH:MM"
    servings: float = 1


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
    s.brand, s.product_name, s.serving_size = body.brand, body.product_name, body.serving_size
    s.ingredients = [SupplementIngredient(**i.model_dump()) for i in body.ingredients]
    s.schedules = [SupplementSchedule(**sc.model_dump()) for sc in body.schedules]


@router.get("/supplements")
def list_supplements(db: Session = Depends(get_db)):
    supps = (db.query(Supplement).filter(Supplement.active.is_(True))
             .order_by(Supplement.product_name).all())
    return [supp_to_dict(s) for s in supps]


@router.post("/supplements", status_code=201)
def create_supplement(body: SupplementIn, db: Session = Depends(get_db)):
    s = Supplement()
    _apply(s, body)
    db.add(s)
    db.commit()
    return {"id": s.id}


@router.put("/supplements/{supp_id}")
def update_supplement(supp_id: int, body: SupplementIn,
                      db: Session = Depends(get_db)):
    s = db.get(Supplement, supp_id)
    if s is None or not s.active:
        raise HTTPException(404, "영양제를 찾을 수 없습니다")
    _apply(s, body)
    db.commit()
    return supp_to_dict(s)


@router.delete("/supplements/{supp_id}", status_code=204)
def deactivate_supplement(supp_id: int, db: Session = Depends(get_db)):
    s = db.get(Supplement, supp_id)
    if s is None:
        raise HTTPException(404, "영양제를 찾을 수 없습니다")
    s.active = False  # soft delete — intake history stays
    db.commit()


class IntakeIn(BaseModel):
    schedule_id: int
    date: date_type
    status: str  # taken | skipped


@router.post("/intake")
def upsert_intake(body: IntakeIn, db: Session = Depends(get_db)):
    if body.status not in ("taken", "skipped"):
        raise HTTPException(422, "status는 taken 또는 skipped여야 합니다")
    if db.get(SupplementSchedule, body.schedule_id) is None:
        raise HTTPException(404, "스케줄을 찾을 수 없습니다")
    log = (db.query(IntakeLog)
           .filter_by(schedule_id=body.schedule_id, date=body.date).first())
    if log:
        log.status = body.status
    else:
        db.add(IntakeLog(schedule_id=body.schedule_id, date=body.date,
                         status=body.status))
    db.commit()
    return {"ok": True}
```

`main.py`: extend router imports — `from .routers import meals, metrics, supplements` + `app.include_router(supplements.router)`.

Caution: `PUT` replaces child rows, which deletes old `SupplementSchedule` rows that `IntakeLog` references. SQLite without FK enforcement allows orphan logs; they simply stop appearing in the calendar (their schedule is gone). Acceptable for Phase 1. `# ponytail: schedule replacement orphans old intake logs — revisit if adherence stats (Phase 2) need them`

- [ ] **Step 4: Run tests, verify pass**

```powershell
.venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: add supplements, schedules and intake log API"
```

---

### Task 7: Calendar feed (schedule expansion)

**Files:**
- Create: `backend/app/routers/calendar.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_calendar.py`

**Interfaces:**
- Consumes: `meal_to_dict` from `app.routers.meals`; models.
- Produces:
  - Pure function `expand_schedules(schedules, logs, start, end) -> list[dict]` — slot dicts `{date, time, schedule_id, supplement_id, supplement_name, servings, status}`, `status` ∈ `taken|skipped|pending`, sorted by (date, time).
  - `GET /api/calendar?start=YYYY-MM-DD&end=YYYY-MM-DD` → `{"meals": [...], "supplement_slots": [...]}`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_calendar.py`:
```python
from datetime import date


def _make_supp(db_session_factory):
    from app.models import IntakeLog, Supplement, SupplementSchedule
    db = db_session_factory()
    s = Supplement(product_name="비타민D")
    s.schedules.append(SupplementSchedule(
        days_of_week="02", time_of_day="09:00", servings=1))  # Mon, Wed
    db.add(s)
    db.commit()
    db.add(IntakeLog(schedule_id=s.schedules[0].id,
                     date=date(2026, 7, 27), status="taken"))  # Mon
    db.commit()
    return db


def test_expand_schedules(db_session_factory):
    from app.models import IntakeLog, SupplementSchedule
    from app.routers.calendar import expand_schedules
    db = _make_supp(db_session_factory)
    schedules = db.query(SupplementSchedule).all()
    logs = db.query(IntakeLog).all()

    # 2026-07-27 Mon … 2026-08-02 Sun
    slots = expand_schedules(schedules, logs,
                             date(2026, 7, 27), date(2026, 8, 2))
    assert len(slots) == 2  # Mon + Wed
    assert slots[0] == {"date": "2026-07-27", "time": "09:00",
                        "schedule_id": schedules[0].id,
                        "supplement_id": schedules[0].supplement_id,
                        "supplement_name": "비타민D", "servings": 1,
                        "status": "taken"}
    assert slots[1]["date"] == "2026-07-29"
    assert slots[1]["status"] == "pending"


def test_calendar_endpoint(auth_client, db_session_factory):
    _make_supp(db_session_factory)
    auth_client.post("/api/meals", json={
        "eaten_at": "2026-07-27T12:00:00", "dish_name": "비빔밥",
        "items": []})
    res = auth_client.get("/api/calendar",
                          params={"start": "2026-07-27", "end": "2026-08-02"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["meals"]) == 1
    assert len(body["supplement_slots"]) == 2


def test_inactive_supplement_excluded(auth_client, db_session_factory):
    db = _make_supp(db_session_factory)
    from app.models import Supplement
    db.query(Supplement).one().active = False
    db.commit()
    res = auth_client.get("/api/calendar",
                          params={"start": "2026-07-27", "end": "2026-08-02"})
    assert res.json()["supplement_slots"] == []
```

- [ ] **Step 2: Run tests, verify fail**

```powershell
.venv\Scripts\python -m pytest tests/test_calendar.py -v
```
Expected: FAIL — import error.

- [ ] **Step 3: Implement calendar router**

`backend/app/routers/calendar.py`:
```python
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from ..auth import require_auth
from ..db import get_db
from ..models import IntakeLog, Meal, Supplement, SupplementSchedule
from .meals import meal_to_dict

router = APIRouter(prefix="/api/calendar", tags=["calendar"],
                   dependencies=[Depends(require_auth)])


def expand_schedules(schedules: list[SupplementSchedule],
                     logs: list[IntakeLog],
                     start: date, end: date) -> list[dict]:
    log_map = {(l.schedule_id, l.date): l.status for l in logs}
    slots = []
    d = start
    while d <= end:
        for s in schedules:
            if str(d.weekday()) in s.days_of_week:
                slots.append({
                    "date": d.isoformat(),
                    "time": s.time_of_day,
                    "schedule_id": s.id,
                    "supplement_id": s.supplement_id,
                    "supplement_name": s.supplement.product_name,
                    "servings": s.servings,
                    "status": log_map.get((s.id, d), "pending"),
                })
        d += timedelta(days=1)
    slots.sort(key=lambda x: (x["date"], x["time"]))
    return slots


@router.get("")
def calendar_feed(start: date, end: date, db: Session = Depends(get_db)):
    lo = datetime.combine(start, time.min)
    hi = datetime.combine(end + timedelta(days=1), time.min)
    meals = (db.query(Meal)
             .filter(Meal.eaten_at >= lo, Meal.eaten_at < hi)
             .order_by(Meal.eaten_at).all())
    schedules = (db.query(SupplementSchedule)
                 .join(Supplement)
                 .filter(Supplement.active.is_(True))
                 .options(joinedload(SupplementSchedule.supplement))
                 .all())
    logs = (db.query(IntakeLog)
            .filter(IntakeLog.date >= start, IntakeLog.date <= end).all())
    return {"meals": [meal_to_dict(m) for m in meals],
            "supplement_slots": expand_schedules(schedules, logs, start, end)}
```

`main.py`: `from .routers import calendar, meals, metrics, supplements` + `app.include_router(calendar.router)`.

- [ ] **Step 4: Run tests, verify pass**

```powershell
.venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: add combined calendar feed with schedule expansion"
```

---

### Task 8: Nutrient resolution (식약처 DB → GPT fallback)

**Files:**
- Create: `backend/app/nutrition.py`
- Modify: `backend/app/routers/meals.py` (`create_meal` calls resolver)
- Test: `backend/tests/test_nutrition.py`

**Interfaces:**
- Consumes: `settings` (`mfds_api_key`, `openai_api_key`, `openai_model_mini`).
- Produces:
  - `NUTRIENT_KEYS: list[str]` — the canonical nutrient vocabulary (Phase 2 aggregates over these)
  - `resolve_nutrients(name: str, amount: str) -> tuple[dict | None, str]` — `(values, source)`, `source` ∈ `"mfds_db" | "ai_estimate" | "none"`. Never raises — any failure falls through to the next source.
  - `_parse_grams(amount: str) -> float | None` (internal, tested)

- [ ] **Step 1: Write failing tests**

`backend/tests/test_nutrition.py`:
```python
import json


def test_parse_grams():
    from app.nutrition import _parse_grams
    assert _parse_grams("100g") == 100
    assert _parse_grams("150 g") == 150
    assert _parse_grams("0.5kg") == 500
    assert _parse_grams("1공기") is None
    assert _parse_grams("") is None


def test_mfds_lookup_scaling(monkeypatch):
    from app import nutrition
    from app.config import settings
    monkeypatch.setattr(settings, "mfds_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_api_key", "")

    canned = {"body": {"items": [
        {"FOOD_NM_KR": "김치찌개",
         "AMT_NUM1": "45.0", "AMT_NUM3": "3.5", "AMT_NUM4": "2.0",
         "AMT_NUM6": "4.0", "AMT_NUM7": "1.5", "AMT_NUM8": "1.2",
         "AMT_NUM9": "30.0", "AMT_NUM10": "0.8", "AMT_NUM12": "200.0",
         "AMT_NUM13": "500.0"}]}}

    class FakeResponse:
        status_code = 200
        def json(self):
            return canned
        def raise_for_status(self):
            pass

    monkeypatch.setattr(nutrition.httpx, "get",
                        lambda *a, **kw: FakeResponse())

    values, source = nutrition.resolve_nutrients("김치찌개", "200g")
    assert source == "mfds_db"
    assert values["kcal"] == 90.0        # 45 per 100g × 200g
    assert values["sodium_mg"] == 1000.0


def test_ai_fallback(monkeypatch):
    from app import nutrition
    from app.config import settings
    monkeypatch.setattr(settings, "mfds_api_key", "")   # no MFDS
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    ai_json = {k: 1.0 for k in nutrition.NUTRIENT_KEYS}

    class FakeMsg:
        content = json.dumps(ai_json)
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
        def __init__(self, **kw):
            self.chat = FakeChat()

    monkeypatch.setattr(nutrition, "OpenAI", FakeClient)

    values, source = nutrition.resolve_nutrients("비빔밥", "1그릇")
    assert source == "ai_estimate"
    assert values["kcal"] == 1.0


def test_no_sources_configured(monkeypatch):
    from app import nutrition
    from app.config import settings
    monkeypatch.setattr(settings, "mfds_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    assert nutrition.resolve_nutrients("뭔가", "100g") == (None, "none")


def test_meal_create_resolves(auth_client, monkeypatch):
    from app.routers import meals as meals_module
    monkeypatch.setattr(meals_module, "resolve_nutrients",
                        lambda name, amount: ({"kcal": 42.0}, "ai_estimate"))
    auth_client.post("/api/meals", json={
        "eaten_at": "2026-07-29T12:00:00", "dish_name": "테스트",
        "items": [{"name": "밥", "amount": "1공기"}]})
    meals = auth_client.get("/api/meals",
                            params={"start": "2026-07-29",
                                    "end": "2026-07-29"}).json()
    item = meals[0]["items"][0]
    assert item["nutrient_source"] == "ai_estimate"
    assert item["nutrients"]["kcal"] == 42.0
```

- [ ] **Step 2: Run tests, verify fail**

```powershell
.venv\Scripts\python -m pytest tests/test_nutrition.py -v
```
Expected: FAIL — `app.nutrition` missing.

- [ ] **Step 3: Implement nutrition module**

`backend/app/nutrition.py`:
```python
import json
import re

import httpx
from openai import OpenAI

from .config import settings

NUTRIENT_KEYS = [
    "kcal", "carb_g", "protein_g", "fat_g", "fiber_g", "sugar_g",
    "sodium_mg", "potassium_mg", "calcium_mg", "iron_mg", "magnesium_mg",
    "zinc_mg", "vitamin_a_ug", "vitamin_c_mg", "vitamin_d_ug",
    "vitamin_b12_ug", "folate_ug", "omega3_g",
]

MFDS_URL = ("https://apis.data.go.kr/1471000/FoodNtrCpntDbInfo02/"
            "getFoodNtrCpntDbInq02")
# ponytail: field mapping taken from 공공데이터포털 문서 #15127578 (식약처 식품영양성분DB).
# Verify against a live response with a real serviceKey on first use; unmapped keys stay None.
MFDS_FIELD_MAP = {  # our key -> API field, values per 100g
    "kcal": "AMT_NUM1", "protein_g": "AMT_NUM3", "fat_g": "AMT_NUM4",
    "carb_g": "AMT_NUM6", "sugar_g": "AMT_NUM7", "fiber_g": "AMT_NUM8",
    "calcium_mg": "AMT_NUM9", "iron_mg": "AMT_NUM10",
    "potassium_mg": "AMT_NUM12", "sodium_mg": "AMT_NUM13",
    "vitamin_a_ug": "AMT_NUM14", "vitamin_c_mg": "AMT_NUM21",
}

_GRAMS_RE = re.compile(r"^\s*([\d.]+)\s*(g|kg)\s*$", re.IGNORECASE)


def _parse_grams(amount: str) -> float | None:
    m = _GRAMS_RE.match(amount or "")
    if not m:
        return None
    val = float(m.group(1))
    return val * 1000 if m.group(2).lower() == "kg" else val


def _mfds_lookup(name: str, grams: float) -> dict | None:
    try:
        res = httpx.get(MFDS_URL, params={
            "serviceKey": settings.mfds_api_key,
            "FOOD_NM_KR": name, "type": "json", "numOfRows": 1,
        }, timeout=10)
        res.raise_for_status()
        items = res.json().get("body", {}).get("items", [])
        if not items:
            return None
        row = items[0]
        factor = grams / 100.0
        out: dict[str, float | None] = {k: None for k in NUTRIENT_KEYS}
        for key, field in MFDS_FIELD_MAP.items():
            raw = row.get(field)
            if raw not in (None, "", "-"):
                out[key] = round(float(raw) * factor, 2)
        return out if out["kcal"] is not None else None
    except Exception:
        return None  # any failure → fall through to next source


def _ai_estimate(name: str, amount: str) -> dict | None:
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        prompt = (
            "다음 음식의 영양성분을 추정해 JSON으로만 답하세요. "
            f"음식: {name}, 양: {amount or '보통 1인분'}. "
            f"키는 정확히 다음만 사용: {', '.join(NUTRIENT_KEYS)}. "
            "값은 숫자(해당 양 전체 기준), 모르면 null."
        )
        res = client.chat.completions.create(
            model=settings.openai_model_mini,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = json.loads(res.choices[0].message.content)
        return {k: (float(data[k]) if isinstance(data.get(k), (int, float))
                    else None)
                for k in NUTRIENT_KEYS}
    except Exception:
        return None


def resolve_nutrients(name: str, amount: str) -> tuple[dict | None, str]:
    grams = _parse_grams(amount)
    if settings.mfds_api_key and grams is not None:
        values = _mfds_lookup(name, grams)
        if values:
            return values, "mfds_db"
    if settings.openai_api_key:
        values = _ai_estimate(name, amount)
        if values:
            return values, "ai_estimate"
    return None, "none"
```

- [ ] **Step 4: Wire into meal creation**

In `backend/app/routers/meals.py`, add import:
```python
from ..nutrition import resolve_nutrients
```
Replace the item loop in `create_meal` with:
```python
    for it in body.items:
        values, source = resolve_nutrients(it.name, it.amount)
        meal.items.append(MealItem(
            name=it.name, amount=it.amount,
            nutrients=json.dumps(values) if values else None,
            nutrient_source=source))
```

Note: resolution is synchronous in the request — one MFDS/OpenAI call per item, a multi-item meal saves in a few seconds. `# ponytail: sync resolution; move to background task if saving feels slow`

- [ ] **Step 5: Run all tests, verify pass**

```powershell
.venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass (existing meal test still passes — no keys configured in tests → source "none").

- [ ] **Step 6: Commit**

```powershell
git add -A
git commit -m "feat: resolve meal item nutrients via MFDS DB with GPT fallback"
```

---

### Task 9: Frontend shell (api client, login, tabs, smoke test)

**Files:**
- Create: `frontend/src/api.ts`, `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/MyDataPage.tsx` (stub), `frontend/src/pages/CalendarPage.tsx` (stub), `frontend/src/pages/SupplementsPage.tsx` (stub), `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/main.tsx`
- Delete: `frontend/src/App.css`, Vite demo assets

**Interfaces:**
- Produces: `api<T>(path, opts?) -> Promise<T>` (JSON fetch, redirects to `/login` on 401); routes `/login`, `/data`, `/calendar`, `/supplements`; bottom `TabBar`. Stub pages are replaced in Tasks 10–12.

- [ ] **Step 1: Write failing smoke test**

`frontend/src/App.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders tab bar", () => {
  render(<App />);
  expect(screen.getByText("내 데이터")).toBeDefined();
  expect(screen.getByText("캘린더")).toBeDefined();
  expect(screen.getByText("영양제")).toBeDefined();
});
```

- [ ] **Step 2: Run, verify fail**

```powershell
cd frontend; npm test
```
Expected: FAIL (App is Vite demo).

- [ ] **Step 3: Implement shell**

`frontend/src/api.ts`:
```ts
export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...opts,
  });
  if (res.status === 401 && !location.pathname.startsWith("/login")) {
    location.href = "/login";
    throw new Error("unauthorized");
  }
  if (!res.ok) throw new Error(await res.text());
  if (res.status === 204) return undefined as T;
  return res.json();
}
```

`frontend/src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

`frontend/src/App.tsx`:
```tsx
import { BrowserRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import MyDataPage from "./pages/MyDataPage";
import CalendarPage from "./pages/CalendarPage";
import SupplementsPage from "./pages/SupplementsPage";

const TABS = [
  { to: "/data", label: "내 데이터", icon: "📊" },
  { to: "/calendar", label: "캘린더", icon: "📅" },
  { to: "/supplements", label: "영양제", icon: "💊" },
];

function TabBar() {
  return (
    <nav className="fixed bottom-0 inset-x-0 bg-white border-t border-slate-200">
      <div className="max-w-lg mx-auto flex">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center py-2 text-xs min-h-11 ${
                isActive ? "text-sky-600 font-semibold" : "text-slate-500"
              }`
            }
          >
            <span className="text-lg leading-none">{t.icon}</span>
            {t.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 pb-20 text-slate-800">
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/data" element={<MyDataPage />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/supplements" element={<SupplementsPage />} />
          <Route path="*" element={<Navigate to="/data" replace />} />
        </Routes>
        <TabBar />
      </div>
    </BrowserRouter>
  );
}
```

`frontend/src/pages/LoginPage.tsx`:
```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      navigate("/data");
    } catch {
      setError("비밀번호가 올바르지 않습니다");
    }
  }

  return (
    <div className="max-w-lg mx-auto px-4 pt-24">
      <h1 className="text-2xl font-bold text-center mb-8">MyHub</h1>
      <form onSubmit={submit} className="bg-white rounded-xl p-6 shadow-sm space-y-4">
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="비밀번호"
          className="w-full border border-slate-300 rounded-lg px-3 py-3"
        />
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button className="w-full bg-sky-600 text-white rounded-lg py-3 font-semibold">
          로그인
        </button>
      </form>
    </div>
  );
}
```

Stub pages (`MyDataPage.tsx`, `CalendarPage.tsx`, `SupplementsPage.tsx`) — same pattern, e.g.:
```tsx
export default function MyDataPage() {
  return <div className="max-w-lg mx-auto px-4 pt-8">내 데이터 — 준비 중</div>;
}
```

Delete `frontend/src/App.css` and demo asset imports.

- [ ] **Step 4: Run test + build, verify pass**

```powershell
npm test; npm run build
```
Expected: test passes, build clean.

- [ ] **Step 5: Manual QA**

Run backend (`cd backend; .venv\Scripts\uvicorn app.main:app --reload --port 8000`) + `npm run dev`. Check: `/login` accepts `changeme` (or your `MYHUB_PASSWORD`), redirects to `/data`, tabs switch pages, unauthenticated visit to `/data` API calls bounce to `/login`.

- [ ] **Step 6: Commit**

```powershell
git add -A
git commit -m "feat: add frontend shell with login and bottom tab navigation"
```

---

### Task 10: 내 데이터 page (metric forms + history chart)

**Files:**
- Modify: `frontend/src/pages/MyDataPage.tsx` (replace stub)

**Interfaces:**
- Consumes: `GET /api/metrics/definitions`, `GET /api/metrics/latest`, `GET /api/metrics/entries?code=`, `POST /api/metrics/entries`, `GET/PUT /api/profile`, `api()` helper.

**Chart spec (validated):** single series — no legend, line `#0284c7` 2px, dots r=3 / activeDot r=5, muted `#64748b` 11px axis ink, horizontal-only `#e2e8f0` grid, tooltip on hover, normal-range `ReferenceArea` in `#10b981` at 8% opacity.

- [ ] **Step 1: Implement page**

`frontend/src/pages/MyDataPage.tsx`:
```tsx
import { useEffect, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";

interface MetricDef {
  code: string; name_ko: string; unit: string; domain: string;
  input_type: string; range_low: number | null; range_high: number | null;
}
interface Entry {
  id: number; metric_code: string; value_num: number | null;
  value_text: string | null; measured_at: string;
}
type Latest = Record<string, { value_num: number | null; value_text: string | null; measured_at: string }>;

const DOMAIN_LABELS: Record<string, string> = {
  body: "신체 기본", lab: "혈액검사", lifestyle: "생활습관", symptom: "증상",
};
const DOMAIN_ORDER = ["body", "lab", "lifestyle", "symptom"];
const SCALE_LABELS = ["없음", "가끔", "자주", "심함"];

function HistoryChart({ def, entries }: { def: MetricDef; entries: Entry[] }) {
  const data = entries
    .filter((e) => e.value_num !== null)
    .map((e) => ({ x: e.measured_at.slice(5, 10), y: e.value_num }))
    .reverse();
  if (data.length < 2)
    return <p className="text-sm text-slate-400 py-3">기록이 2개 이상이면 그래프가 표시됩니다</p>;
  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey="x" tick={{ fontSize: 11, fill: "#64748b" }}
               tickLine={false} axisLine={{ stroke: "#e2e8f0" }} />
        <YAxis tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false}
               axisLine={false} width={40} domain={["auto", "auto"]} />
        <Tooltip formatter={(v) => [`${v} ${def.unit}`, def.name_ko]} />
        {def.range_low !== null && def.range_high !== null && (
          <ReferenceArea y1={def.range_low} y2={def.range_high}
                         fill="#10b981" fillOpacity={0.08} />
        )}
        <Line type="monotone" dataKey="y" stroke="#0284c7" strokeWidth={2}
              dot={{ r: 3 }} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function MetricRow({ def, latest, onSaved }: {
  def: MetricDef;
  latest: Latest[string] | undefined;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && def.input_type !== "text")
      api<Entry[]>(`/api/metrics/entries?code=${def.code}`).then(setEntries);
  }, [open, def]);

  async function save(valueNum: number | null, valueText: string | null) {
    setSaving(true);
    try {
      await api("/api/metrics/entries", {
        method: "POST",
        body: JSON.stringify({
          metric_code: def.code, value_num: valueNum, value_text: valueText,
        }),
      });
      setInput("");
      onSaved();
      if (open && def.input_type !== "text")
        api<Entry[]>(`/api/metrics/entries?code=${def.code}`).then(setEntries);
    } finally {
      setSaving(false);
    }
  }

  const latestLabel = latest
    ? def.input_type === "scale" && latest.value_num !== null
      ? SCALE_LABELS[latest.value_num]
      : def.input_type === "text"
        ? latest.value_text
        : `${latest.value_num} ${def.unit}`
    : "—";

  return (
    <div className="border-b border-slate-100 last:border-0 py-3">
      <button className="w-full flex justify-between items-center min-h-11"
              onClick={() => setOpen(!open)}>
        <span>{def.name_ko}</span>
        <span className="text-slate-500 text-sm">{latestLabel} {open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="pt-2 space-y-3">
          {def.input_type !== "text" && <HistoryChart def={def} entries={entries} />}
          {def.input_type === "scale" ? (
            <div className="flex gap-2">
              {SCALE_LABELS.map((label, i) => (
                <button key={i} disabled={saving}
                        onClick={() => save(i, null)}
                        className="flex-1 py-2 rounded-lg border border-slate-300 text-sm active:bg-sky-50">
                  {label}
                </button>
              ))}
            </div>
          ) : (
            <div className="flex gap-2">
              <input
                type={def.input_type === "number" ? "number" : "text"}
                inputMode={def.input_type === "number" ? "decimal" : undefined}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={def.unit || "입력"}
                className="flex-1 border border-slate-300 rounded-lg px-3 py-2"
              />
              <button
                disabled={saving || !input}
                onClick={() =>
                  def.input_type === "number"
                    ? save(Number(input), null)
                    : save(null, input)
                }
                className="bg-sky-600 text-white rounded-lg px-4 disabled:opacity-40">
                저장
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface ProfileData { name: string; sex: string | null; birth_date: string | null; }

function ProfileCard() {
  const [profile, setProfile] = useState<ProfileData>({ name: "", sex: null, birth_date: null });
  const [saved, setSaved] = useState(false);

  useEffect(() => { api<ProfileData>("/api/profile").then(setProfile); }, []);

  async function save() {
    await api("/api/profile", { method: "PUT", body: JSON.stringify(profile) });
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  return (
    <section className="bg-white rounded-xl shadow-sm p-4 space-y-2">
      <h2 className="text-sm font-semibold text-slate-500">프로필</h2>
      <div className="flex gap-2">
        <input value={profile.name} placeholder="이름"
               onChange={(e) => setProfile({ ...profile, name: e.target.value })}
               className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm" />
        <select value={profile.sex ?? ""}
                onChange={(e) => setProfile({ ...profile, sex: e.target.value || null })}
                className="border border-slate-300 rounded-lg px-2 text-sm">
          <option value="">성별</option>
          <option value="M">남</option>
          <option value="F">여</option>
        </select>
        <input type="date" value={profile.birth_date ?? ""}
               onChange={(e) => setProfile({ ...profile, birth_date: e.target.value || null })}
               className="border border-slate-300 rounded-lg px-2 text-sm" />
      </div>
      <button onClick={save}
              className="w-full bg-sky-600 text-white rounded-lg py-2 text-sm">
        {saved ? "저장됨 ✓" : "프로필 저장"}
      </button>
    </section>
  );
}

export default function MyDataPage() {
  const [defs, setDefs] = useState<MetricDef[]>([]);
  const [latest, setLatest] = useState<Latest>({});

  function reload() {
    api<Latest>("/api/metrics/latest").then(setLatest);
  }
  useEffect(() => {
    api<MetricDef[]>("/api/metrics/definitions").then(setDefs);
    reload();
  }, []);

  return (
    <div className="max-w-lg mx-auto px-4 pt-6 space-y-6">
      <h1 className="text-xl font-bold">내 데이터</h1>
      <p className="text-sm text-slate-500">
        아는 항목만 입력하세요. 입력한 데이터만 분석에 사용됩니다.
      </p>
      <ProfileCard />
      {DOMAIN_ORDER.map((domain) => (
        <section key={domain} className="bg-white rounded-xl shadow-sm px-4 py-2">
          <h2 className="text-sm font-semibold text-slate-500 pt-2">
            {DOMAIN_LABELS[domain]}
          </h2>
          {defs.filter((d) => d.domain === domain).map((d) => (
            <MetricRow key={d.code} def={d} latest={latest[d.code]} onSaved={reload} />
          ))}
        </section>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Build + manual QA**

```powershell
npm run build
```
Then with both servers running, verify on a phone-width viewport: profile card saves name/sex/birth date and survives reload; four domain sections render; entering 몸무게 saves and shows as latest; two+ entries show the chart with green normal band; scale metric saves via label buttons; text metric (복용 중인 약) saves; chart tooltip works.

- [ ] **Step 3: Commit**

```powershell
git add -A
git commit -m "feat: add my-data page with sparse metric forms and history charts"
```

---

### Task 11: 캘린더 page (month/week/day, meal logging, intake checks)

**Files:**
- Modify: `frontend/src/pages/CalendarPage.tsx` (replace stub)

**Interfaces:**
- Consumes: `GET /api/calendar?start&end`, `POST /api/meals`, `DELETE /api/meals/{id}`, `POST /api/intake`.

- [ ] **Step 1: Implement page**

`frontend/src/pages/CalendarPage.tsx`:
```tsx
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";

interface MealItemOut { id: number; name: string; amount: string; nutrient_source: string; }
interface MealOut { id: number; eaten_at: string; dish_name: string; items: MealItemOut[]; }
interface Slot {
  date: string; time: string; schedule_id: number; supplement_id: number;
  supplement_name: string; servings: number; status: "taken" | "skipped" | "pending";
}
type View = "month" | "week" | "day";

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const startOfWeek = (d: Date) => addDays(d, -((d.getDay() + 6) % 7)); // Monday
const DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"];

function rangeFor(view: View, anchor: Date): [Date, Date] {
  if (view === "day") return [anchor, anchor];
  if (view === "week") return [startOfWeek(anchor), addDays(startOfWeek(anchor), 6)];
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const last = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
  return [first, last];
}

function AddMealForm({ date, onDone }: { date: string; onDone: () => void }) {
  const [dish, setDish] = useState("");
  const [time, setTime] = useState("12:00");
  const [items, setItems] = useState([{ name: "", amount: "" }]);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await api("/api/meals", {
        method: "POST",
        body: JSON.stringify({
          eaten_at: `${date}T${time}:00`,
          dish_name: dish,
          items: items.filter((i) => i.name.trim()),
        }),
      });
      onDone();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-4 space-y-3">
      <div className="flex gap-2">
        <input value={dish} onChange={(e) => setDish(e.target.value)}
               placeholder="음식 이름 (예: 김치찌개)"
               className="flex-1 border border-slate-300 rounded-lg px-3 py-2" />
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)}
               className="border border-slate-300 rounded-lg px-2" />
      </div>
      {items.map((it, idx) => (
        <div key={idx} className="flex gap-2">
          <input value={it.name} placeholder="재료"
                 onChange={(e) => setItems(items.map((x, i) => i === idx ? { ...x, name: e.target.value } : x))}
                 className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          <input value={it.amount} placeholder="양 (예: 100g, 반 모)"
                 onChange={(e) => setItems(items.map((x, i) => i === idx ? { ...x, amount: e.target.value } : x))}
                 className="w-32 border border-slate-200 rounded-lg px-3 py-2 text-sm" />
        </div>
      ))}
      <div className="flex gap-2">
        <button onClick={() => setItems([...items, { name: "", amount: "" }])}
                className="text-sm text-sky-600 py-2">+ 재료 추가</button>
        <button onClick={save} disabled={saving || !dish.trim()}
                className="ml-auto bg-sky-600 text-white rounded-lg px-4 py-2 text-sm disabled:opacity-40">
          {saving ? "영양성분 계산 중…" : "저장"}
        </button>
      </div>
    </div>
  );
}

function DayDetail({ date, meals, slots, reload }: {
  date: string; meals: MealOut[]; slots: Slot[]; reload: () => void;
}) {
  const [adding, setAdding] = useState(false);

  async function setIntake(slot: Slot, status: "taken" | "skipped") {
    await api("/api/intake", {
      method: "POST",
      body: JSON.stringify({ schedule_id: slot.schedule_id, date, status }),
    });
    reload();
  }
  async function removeMeal(id: number) {
    await api(`/api/meals/${id}`, { method: "DELETE" });
    reload();
  }

  return (
    <div className="space-y-4">
      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-slate-500">영양제</h3>
        {slots.length === 0 && <p className="text-sm text-slate-400">예정된 영양제가 없습니다</p>}
        {slots.map((s) => (
          <div key={s.schedule_id} className="bg-white rounded-xl shadow-sm p-3 flex items-center gap-2">
            <span className="text-sm">{s.time} · {s.supplement_name} {s.servings > 1 ? `×${s.servings}` : ""}</span>
            <div className="ml-auto flex gap-1">
              <button onClick={() => setIntake(s, "taken")}
                      className={`px-3 py-2 rounded-lg text-sm ${s.status === "taken" ? "bg-emerald-500 text-white" : "border border-slate-300"}`}>
                복용 ✓
              </button>
              <button onClick={() => setIntake(s, "skipped")}
                      className={`px-3 py-2 rounded-lg text-sm ${s.status === "skipped" ? "bg-slate-400 text-white" : "border border-slate-300"}`}>
                건너뜀
              </button>
            </div>
          </div>
        ))}
      </section>
      <section className="space-y-2">
        <div className="flex items-center">
          <h3 className="text-sm font-semibold text-slate-500">식사</h3>
          <button onClick={() => setAdding(!adding)} className="ml-auto text-sm text-sky-600 py-2">
            {adding ? "닫기" : "+ 식사 기록"}
          </button>
        </div>
        {adding && <AddMealForm date={date} onDone={() => { setAdding(false); reload(); }} />}
        {meals.map((m) => (
          <div key={m.id} className="bg-white rounded-xl shadow-sm p-3">
            <div className="flex items-center">
              <span className="font-medium">{m.eaten_at.slice(11, 16)} · {m.dish_name}</span>
              <button onClick={() => removeMeal(m.id)} className="ml-auto text-xs text-slate-400 py-2">삭제</button>
            </div>
            {m.items.length > 0 && (
              <p className="text-xs text-slate-500 mt-1">
                {m.items.map((i) => `${i.name}${i.nutrient_source === "ai_estimate" ? "*" : ""}`).join(", ")}
              </p>
            )}
          </div>
        ))}
        {meals.length > 0 && meals.some((m) => m.items.some((i) => i.nutrient_source === "ai_estimate")) && (
          <p className="text-xs text-slate-400">* AI 추정 영양성분</p>
        )}
      </section>
    </div>
  );
}

export default function CalendarPage() {
  const [view, setView] = useState<View>("day");
  const [anchor, setAnchor] = useState(new Date());
  const [meals, setMeals] = useState<MealOut[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);

  const [start, end] = rangeFor(view, anchor);

  const reload = useCallback(() => {
    api<{ meals: MealOut[]; supplement_slots: Slot[] }>(
      `/api/calendar?start=${iso(start)}&end=${iso(end)}`
    ).then((d) => { setMeals(d.meals); setSlots(d.supplement_slots); });
  }, [view, anchor]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(reload, [reload]);

  function shift(n: number) {
    if (view === "day") setAnchor(addDays(anchor, n));
    else if (view === "week") setAnchor(addDays(anchor, n * 7));
    else setAnchor(new Date(anchor.getFullYear(), anchor.getMonth() + n, 1));
  }

  const title =
    view === "day"
      ? `${anchor.getMonth() + 1}월 ${anchor.getDate()}일 (${DAY_NAMES[(anchor.getDay() + 6) % 7]})`
      : view === "week"
        ? `${start.getMonth() + 1}/${start.getDate()} – ${end.getMonth() + 1}/${end.getDate()}`
        : `${anchor.getFullYear()}년 ${anchor.getMonth() + 1}월`;

  const byDate = (arr: { [k: string]: any }[], key: string, d: string) =>
    arr.filter((x) => String(x[key]).slice(0, 10) === d);

  return (
    <div className="max-w-lg mx-auto px-4 pt-6 space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-bold">캘린더</h1>
        <div className="ml-auto flex rounded-lg border border-slate-300 overflow-hidden text-sm">
          {(["month", "week", "day"] as View[]).map((v) => (
            <button key={v} onClick={() => setView(v)}
                    className={`px-3 py-2 ${view === v ? "bg-sky-600 text-white" : "bg-white"}`}>
              {v === "month" ? "월" : v === "week" ? "주" : "일"}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <button onClick={() => shift(-1)} className="px-3 py-2 text-slate-500">◀</button>
        <span className="font-medium">{title}</span>
        <button onClick={() => shift(1)} className="px-3 py-2 text-slate-500">▶</button>
      </div>

      {view === "month" && (
        <div className="bg-white rounded-xl shadow-sm p-2">
          <div className="grid grid-cols-7 text-center text-xs text-slate-400 pb-1">
            {DAY_NAMES.map((d) => <span key={d}>{d}</span>)}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {Array.from({ length: (start.getDay() + 6) % 7 }).map((_, i) => <span key={`b${i}`} />)}
            {Array.from({ length: end.getDate() }).map((_, i) => {
              const d = iso(new Date(anchor.getFullYear(), anchor.getMonth(), i + 1));
              const hasMeal = byDate(meals, "eaten_at", d).length > 0;
              const daySlots = byDate(slots, "date", d);
              const allTaken = daySlots.length > 0 && daySlots.every((s) => s.status === "taken");
              return (
                <button key={d}
                        onClick={() => { setAnchor(new Date(d)); setView("day"); }}
                        className="aspect-square rounded-lg text-sm flex flex-col items-center justify-center hover:bg-sky-50">
                  {i + 1}
                  <span className="flex gap-0.5 h-1.5">
                    {hasMeal && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />}
                    {daySlots.length > 0 && (
                      <span className={`w-1.5 h-1.5 rounded-full ${allTaken ? "bg-sky-600" : "bg-slate-300"}`} />
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {view === "week" && (
        <div className="space-y-2">
          {Array.from({ length: 7 }).map((_, i) => {
            const d = iso(addDays(start, i));
            const dayMeals = byDate(meals, "eaten_at", d);
            const daySlots = byDate(slots, "date", d) as Slot[];
            return (
              <button key={d} onClick={() => { setAnchor(new Date(d)); setView("day"); }}
                      className="w-full bg-white rounded-xl shadow-sm p-3 text-left">
                <span className="text-sm font-medium">{d.slice(5)} ({DAY_NAMES[i]})</span>
                <p className="text-xs text-slate-500 mt-1">
                  식사 {dayMeals.length}회 · 영양제 {daySlots.filter((s) => s.status === "taken").length}/{daySlots.length}
                </p>
              </button>
            );
          })}
        </div>
      )}

      {view === "day" && (
        <DayDetail date={iso(anchor)}
                   meals={byDate(meals, "eaten_at", iso(anchor)) as MealOut[]}
                   slots={byDate(slots, "date", iso(anchor)) as Slot[]}
                   reload={reload} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Build + manual QA**

```powershell
npm run build
```
Manual: day view shows supplement slots (after Task 12 adds one) with 복용/건너뜀 toggling; meal add form saves with items and shows `*` on AI-estimated items; month view shows dots and tapping a day opens it; week view counts; ◀▶ navigation in all three views.

- [ ] **Step 3: Commit**

```powershell
git add -A
git commit -m "feat: add calendar page with month/week/day views, meal logging and intake checks"
```

---

### Task 12: 영양제 관리 page

**Files:**
- Modify: `frontend/src/pages/SupplementsPage.tsx` (replace stub)

**Interfaces:**
- Consumes: `GET/POST/PUT/DELETE /api/supplements`.

- [ ] **Step 1: Implement page**

`frontend/src/pages/SupplementsPage.tsx`:
```tsx
import { useEffect, useState } from "react";
import { api } from "../api";

interface Ingredient { ingredient_code: string; amount: number; unit: string; }
interface Schedule { id?: number; days_of_week: string; time_of_day: string; servings: number; }
interface Supp {
  id: number; brand: string; product_name: string; serving_size: string;
  ingredients: Ingredient[]; schedules: Schedule[];
}

const DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"];
const INGREDIENT_SUGGESTIONS = [
  "vitamin_a", "vitamin_b1", "vitamin_b2", "vitamin_b6", "vitamin_b12",
  "vitamin_c", "vitamin_d", "vitamin_e", "vitamin_k", "folate", "niacin",
  "biotin", "calcium", "magnesium", "zinc", "iron", "selenium", "potassium",
  "omega3", "lutein", "probiotics", "coenzyme_q10", "milk_thistle",
];
const UNITS = ["mg", "ug", "IU", "g", "억CFU"];

const emptyForm = () => ({
  brand: "", product_name: "", serving_size: "1정",
  ingredients: [{ ingredient_code: "", amount: 0, unit: "mg" }] as Ingredient[],
  schedules: [{ days_of_week: "0123456", time_of_day: "09:00", servings: 1 }] as Schedule[],
});

function SuppForm({ initial, onSaved, onCancel }: {
  initial: (ReturnType<typeof emptyForm> & { id?: number });
  onSaved: () => void; onCancel: () => void;
}) {
  const [form, setForm] = useState(initial);
  const [saving, setSaving] = useState(false);

  function toggleDay(si: number, day: number) {
    const s = form.schedules[si];
    const has = s.days_of_week.includes(String(day));
    const days = has
      ? s.days_of_week.replace(String(day), "")
      : [...s.days_of_week, String(day)].sort().join("");
    setForm({
      ...form,
      schedules: form.schedules.map((x, i) => (i === si ? { ...x, days_of_week: days } : x)),
    });
  }

  async function save() {
    setSaving(true);
    try {
      const body = JSON.stringify({
        ...form,
        ingredients: form.ingredients.filter((i) => i.ingredient_code.trim()),
        schedules: form.schedules.filter((s) => s.days_of_week),
      });
      if (form.id)
        await api(`/api/supplements/${form.id}`, { method: "PUT", body });
      else await api("/api/supplements", { method: "POST", body });
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-4 space-y-3">
      <div className="flex gap-2">
        <input value={form.brand} placeholder="브랜드"
               onChange={(e) => setForm({ ...form, brand: e.target.value })}
               className="w-28 border border-slate-300 rounded-lg px-3 py-2 text-sm" />
        <input value={form.product_name} placeholder="제품명 *"
               onChange={(e) => setForm({ ...form, product_name: e.target.value })}
               className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm" />
        <input value={form.serving_size} placeholder="1회 분량"
               onChange={(e) => setForm({ ...form, serving_size: e.target.value })}
               className="w-20 border border-slate-300 rounded-lg px-3 py-2 text-sm" />
      </div>

      <p className="text-xs font-semibold text-slate-500">성분 (1회 분량 기준)</p>
      <datalist id="ingredients">
        {INGREDIENT_SUGGESTIONS.map((s) => <option key={s} value={s} />)}
      </datalist>
      {form.ingredients.map((ing, idx) => (
        <div key={idx} className="flex gap-2">
          <input list="ingredients" value={ing.ingredient_code} placeholder="성분 (예: vitamin_d)"
                 onChange={(e) => setForm({ ...form, ingredients: form.ingredients.map((x, i) => i === idx ? { ...x, ingredient_code: e.target.value } : x) })}
                 className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          <input type="number" value={ing.amount || ""} placeholder="양"
                 onChange={(e) => setForm({ ...form, ingredients: form.ingredients.map((x, i) => i === idx ? { ...x, amount: Number(e.target.value) } : x) })}
                 className="w-20 border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          <select value={ing.unit}
                  onChange={(e) => setForm({ ...form, ingredients: form.ingredients.map((x, i) => i === idx ? { ...x, unit: e.target.value } : x) })}
                  className="border border-slate-200 rounded-lg px-2 text-sm">
            {UNITS.map((u) => <option key={u}>{u}</option>)}
          </select>
        </div>
      ))}
      <button onClick={() => setForm({ ...form, ingredients: [...form.ingredients, { ingredient_code: "", amount: 0, unit: "mg" }] })}
              className="text-sm text-sky-600 py-1">+ 성분 추가</button>

      <p className="text-xs font-semibold text-slate-500">복용 스케줄</p>
      {form.schedules.map((s, si) => (
        <div key={si} className="space-y-2">
          <div className="flex gap-1">
            {DAY_NAMES.map((d, day) => (
              <button key={d} onClick={() => toggleDay(si, day)}
                      className={`w-9 h-9 rounded-full text-sm ${s.days_of_week.includes(String(day)) ? "bg-sky-600 text-white" : "border border-slate-300"}`}>
                {d}
              </button>
            ))}
          </div>
          <div className="flex gap-2 items-center">
            <input type="time" value={s.time_of_day}
                   onChange={(e) => setForm({ ...form, schedules: form.schedules.map((x, i) => i === si ? { ...x, time_of_day: e.target.value } : x) })}
                   className="border border-slate-200 rounded-lg px-2 py-1 text-sm" />
            <input type="number" min={1} value={s.servings}
                   onChange={(e) => setForm({ ...form, schedules: form.schedules.map((x, i) => i === si ? { ...x, servings: Number(e.target.value) } : x) })}
                   className="w-16 border border-slate-200 rounded-lg px-2 py-1 text-sm" />
            <span className="text-xs text-slate-500">회분</span>
          </div>
        </div>
      ))}

      <div className="flex gap-2 pt-2">
        <button onClick={onCancel} className="flex-1 border border-slate-300 rounded-lg py-2 text-sm">취소</button>
        <button onClick={save} disabled={saving || !form.product_name.trim()}
                className="flex-1 bg-sky-600 text-white rounded-lg py-2 text-sm disabled:opacity-40">
          저장
        </button>
      </div>
    </div>
  );
}

export default function SupplementsPage() {
  const [supps, setSupps] = useState<Supp[]>([]);
  const [editing, setEditing] = useState<(ReturnType<typeof emptyForm> & { id?: number }) | null>(null);

  const reload = () => api<Supp[]>("/api/supplements").then(setSupps);
  useEffect(() => { reload(); }, []);

  async function remove(id: number) {
    if (!confirm("이 영양제를 목록에서 제거할까요? 복용 기록은 유지됩니다.")) return;
    await api(`/api/supplements/${id}`, { method: "DELETE" });
    reload();
  }

  return (
    <div className="max-w-lg mx-auto px-4 pt-6 space-y-4">
      <div className="flex items-center">
        <h1 className="text-xl font-bold">영양제 관리</h1>
        <button onClick={() => setEditing(emptyForm())}
                className="ml-auto bg-sky-600 text-white rounded-lg px-4 py-2 text-sm">
          + 추가
        </button>
      </div>

      {editing && (
        <SuppForm initial={editing}
                  onSaved={() => { setEditing(null); reload(); }}
                  onCancel={() => setEditing(null)} />
      )}

      {supps.map((s) => (
        <div key={s.id} className="bg-white rounded-xl shadow-sm p-4">
          <div className="flex items-start">
            <div>
              <p className="font-medium">{s.product_name}</p>
              <p className="text-xs text-slate-500">{s.brand} · {s.serving_size}</p>
            </div>
            <div className="ml-auto flex gap-3 text-sm">
              <button onClick={() => setEditing({ ...s })} className="text-sky-600 py-2">수정</button>
              <button onClick={() => remove(s.id)} className="text-slate-400 py-2">제거</button>
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            {s.ingredients.map((i) => `${i.ingredient_code} ${i.amount}${i.unit}`).join(" · ")}
          </p>
          {s.schedules.map((sc, i) => (
            <p key={i} className="text-xs text-slate-400 mt-1">
              {[...sc.days_of_week].map((d) => DAY_NAMES[Number(d)]).join(",")} {sc.time_of_day}
              {sc.servings > 1 ? ` ×${sc.servings}` : ""}
            </p>
          ))}
        </div>
      ))}
      {supps.length === 0 && !editing && (
        <p className="text-sm text-slate-400 text-center pt-8">
          영양제를 추가하면 캘린더와 복용 알림에 반영됩니다
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Build + manual QA**

```powershell
npm run build
```
Manual: add 오메가3 with ingredient + daily 09:00 schedule → appears in list; shows in 캘린더 day view as slot; 복용 ✓ persists after reload; edit changes time; 제거 asks confirmation, hides from list, calendar slot gone.

- [ ] **Step 3: Commit**

```powershell
git add -A
git commit -m "feat: add supplement management page with ingredients and schedules"
```

---

### Task 13: Static serving + Docker + ship check

**Files:**
- Modify: `backend/app/main.py` (serve SPA), `backend/app/auth.py` (secure cookie flag)
- Create: `Dockerfile`

**Interfaces:**
- Consumes: everything.
- Produces: `docker build` → single image; `MYHUB_STATIC_DIR` env points at built SPA; cookie `secure` flag via `MYHUB_COOKIE_SECURE` env.

- [ ] **Step 1: SPA serving in main.py**

Append inside `create_app()` after all router includes:
```python
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    from .config import settings

    static_dir = settings.myhub_static_dir
    if static_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"),
                  name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            return FileResponse(static_dir / "index.html")
```

- [ ] **Step 2: Secure cookie flag**

In `backend/app/config.py`, add field:
```python
    myhub_cookie_secure: bool = False
```
In `backend/app/auth.py` `login()`, change `set_cookie` call to include:
```python
    response.set_cookie(COOKIE_NAME, token, max_age=MAX_AGE,
                        httponly=True, samesite="lax",
                        secure=settings.myhub_cookie_secure)
```

- [ ] **Step 3: Dockerfile**

`Dockerfile` (repo root):
```dockerfile
FROM node:22-alpine AS fe
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=fe /fe/dist ./static
ENV MYHUB_STATIC_DIR=/app/static \
    MYHUB_DATA_DIR=/app/data \
    MYHUB_COOKIE_SECURE=true
VOLUME /app/data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Full verification**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/ -v
cd ..\frontend; npm test; npm run build
cd ..; docker build -t myhub .
docker run --rm -p 8000:8000 -e MYHUB_PASSWORD=test -e MYHUB_COOKIE_SECURE=false -v myhub-data:/app/data myhub
```
Expected: all tests pass; open http://localhost:8000 → login with `test` → all three tabs work end-to-end (served by FastAPI, no Vite).

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: serve SPA from FastAPI and add production Dockerfile"
```

---

## Phase 1 exit criteria

- `pytest` green (≈20 tests), `npm test` green, `npm run build` clean, Docker image runs the full app.
- On a phone-width browser: login → enter metrics → see chart → log meal (nutrients resolved, source marked) → add supplement with schedule → check off intake on calendar.
- Cloud deploy itself is Phase 4 (spec §8 task 15); Docker image from this phase is what gets deployed.

## Deferred (per spec)

- Phase 2: evidence base, safety engine, analysis engine, 대시보드, 리포트 — separate plan after Phase 1 lands.
- Phase 3: photo pipeline, AI 채팅, web push.
- Phase 4: weekly jobs, backups, PWA install, deploy.
