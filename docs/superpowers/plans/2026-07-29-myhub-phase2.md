# MyHub Phase 2 — Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Phase 1 logging backbone into an app that warns about
supplement duplication/overdose in real time and produces an on-demand AI
analysis (top-3 lacking nutrients + actions, citation-checked) surfaced on a
new 대시보드 (home) page and a new 리포트 page.

**Architecture:** Two new deterministic-first subsystems on top of the
existing FastAPI/SQLite backend. (1) A pure safety-engine function computes
duplication/overdose/interaction warnings from active supplements —
no LLM involved. (2) An analysis engine assembles a deterministic JSON
snapshot of the user's data, sends it to the OpenAI strong model with a
closed citation list, validates the response against a Pydantic schema
(shape + citation resolution), retries once on failure, and stores the
result. Two new React pages consume these APIs; 대시보드 becomes the new
default route.

**Tech Stack:** Same as Phase 1 (FastAPI, SQLAlchemy 2.x, SQLite, pytest ·
React + Vite + TS + Tailwind v4 + recharts). No new dependencies — `openai`,
`pydantic`/`pydantic-settings` are already in `backend/requirements.txt`.

**Spec:** `docs/superpowers/specs/2026-07-29-myhub-design.md` §3 (evidence_refs,
nutrient_limits), §4.3 (safety engine), §4.4 (analysis engine), §5 (대시보드,
리포트 pages). Phase 2 = spec §8 tasks 6–9.

**Scope note (deviates from spec on one point, deliberately):** Spec §4.4
lists two analysis triggers — "on-demand button + APScheduler weekly job."
The weekly scheduler is explicitly spec'd as **Phase 4 item 13** ("Weekly
auto-analysis job"), so this plan implements the on-demand `분석하기` button
only. `Analysis.trigger` already stores `"manual" | "weekly"` so Phase 4 adding
the scheduler is a pure addition, no migration.

## Global Constraints (Phase 2 additions on top of Phase 1's)

- All new `/api/*` routes require `require_auth` (`dependencies=[Depends(require_auth)]` on the router), same as every Phase 1 router.
- `Base.metadata.create_all` only — no migrations. New tables are pure additions.
- Ingredient codes are free-text strings already in use by `SupplementIngredient.ingredient_code` (see `INGREDIENT_SUGGESTIONS` in `frontend/src/pages/SupplementsPage.tsx`: `vitamin_a`, `vitamin_b1`, `vitamin_b2`, `vitamin_b6`, `vitamin_b12`, `vitamin_c`, `vitamin_d`, `vitamin_e`, `vitamin_k`, `folate`, `niacin`, `biotin`, `calcium`, `magnesium`, `zinc`, `iron`, `selenium`, `potassium`, `omega3`, `lutein`, `probiotics`, `coenzyme_q10`, `milk_thistle`). `nutrient_limits`/`interaction_rules` seed data must use codes from this exact vocabulary or the safety engine silently sees no match — no error, just no warning.
- `# ponytail: nutrient_limits seed values are standard adult (19–64) DRI figures included for structural completeness — verify each against the official KDRIs 2020 tables before relying on them for real dosing decisions.` Carry this disclaimer into the seed file; it is not decorative, it is the mitigation named in spec §9 risk "Curation effort for evidence base."
- Safety engine does no unit conversion — a `nutrient_limits` row only matches ingredients logged with the exact same `unit` string. `# ponytail: add mg⇄µg⇄IU conversion if a real supplement ever uses a mismatched unit; today's seed keeps units consistent per ingredient.`
- LLM output is validated by Pydantic, not trusted as-is: max 3 `top3` entries, ≥3 actions each, every `evidence_ids` value must resolve to a row in the current `evidence_refs` table snapshot passed to the model. One retry with the validation error appended to the prompt; second failure raises `AnalysisError` → router returns `502` with a Korean error message (spec §6: "OpenAI API down → ... analysis & chat show friendly retry message").
- Analysis runs synchronously inside the request (no queue/background job) — acceptable for a single-user, on-demand button per spec §8 Phase 2 scope (see Scope note above).
- Frontend: no new dependencies. Reuse the existing `api<T>()` helper, Tailwind classes (`bg-white rounded-xl shadow-sm p-4`, accent `sky-600`, `max-w-lg mx-auto`), and the intake-toggle / calendar-fetch patterns already in `CalendarPage.tsx`.
- Frontend testing: extend the single `App.test.tsx` smoke test only (tab labels + fetch stub branches for new endpoints). Pages verified by manual QA checklists in their tasks, same as Phase 1.
- Commit after every green test cycle. Commit messages end with `Co-Authored-By: Claude <model name> <noreply@anthropic.com>` — use whichever Claude model is executing the task (Phase 1 commits used both "Claude Fable 5" and "Claude Opus 4.8"; either convention is fine, just be consistent within a single commit).
- Dev runs unchanged: backend `cd backend; .venv\Scripts\uvicorn app.main:app --reload --port 8000`, frontend `cd frontend; npm run dev`.

## File Structure (new/changed files this phase)

```
backend/
  app/
    models.py          # + EvidenceRef, NutrientLimit, InteractionRule, Analysis
    config.py           # + openai_model_strong
    seed.py              # + EVIDENCE_REFS, NUTRIENT_LIMITS, INTERACTION_RULES, seed_evidence_and_limits()
    analysis.py         # NEW — build_analysis_input, AnalysisResult schema, run_analysis()
    main.py              # + seed_evidence_and_limits() call, safety + analysis router includes
    routers/
      metrics.py         # + latest_metrics_dict() extracted for reuse
      safety.py           # NEW — compute_safety_warnings() + GET /api/safety/warnings
      analysis.py         # NEW — POST /api/analysis/run, GET /api/analysis[/latest|/{id}]
  tests/
    test_models.py       # + evidence/safety model roundtrip test
    test_evidence_seed.py # NEW
    test_safety.py        # NEW
    test_analysis_input.py # NEW
    test_analysis.py       # NEW
frontend/
  src/
    App.tsx               # + /dashboard (new default), /report routes + tabs
    App.test.tsx           # + tab labels, fetch stub branches
    pages/
      ReportPage.tsx        # NEW — exports Top3Card, Top3Entry, AnalysisDetail for reuse
      DashboardPage.tsx      # NEW — home page
```

---

### Task 1: Evidence & safety data model + curated seed

**Files:**
- Modify: `backend/app/models.py` (append models)
- Modify: `backend/app/seed.py` (append seed data + function; extend import line)
- Modify: `backend/app/main.py` (call new seed function in lifespan)
- Modify: `backend/tests/test_models.py` (append roundtrip test)
- Create: `backend/tests/test_evidence_seed.py`

**Interfaces:**
- Consumes: `Base` from `app.db`.
- Produces: `EvidenceRef(id, type, nutrient_code, claim_summary, source_url, reliability_grade)`, `NutrientLimit(id, ingredient_code, unit, rda, ul, sex, evidence_id)`, `InteractionRule(id, ingredient_a, ingredient_b, reason, evidence_id)`, `Analysis(id, run_at, trigger, result)`. `seed_evidence_and_limits(db: Session) -> None` (idempotent — no-op if any `EvidenceRef` already exists). Task 2 (safety engine) and Task 3/4 (analysis engine) query these tables directly.

- [ ] **Step 1: Write failing model test**

Append to `backend/tests/test_models.py`:
```python
def test_evidence_and_safety_models_roundtrip(db_session_factory):
    from app.models import Analysis, EvidenceRef, InteractionRule, NutrientLimit

    db = db_session_factory()

    ev = EvidenceRef(type="KDRI", nutrient_code="vitamin_d",
                     claim_summary="비타민D 권장 섭취량",
                     source_url="https://www.mohw.go.kr", reliability_grade="A")
    db.add(ev)
    db.commit()

    db.add(NutrientLimit(ingredient_code="vitamin_d", unit="ug", rda=10, ul=100,
                         sex="ALL", evidence_id=ev.id))
    db.add(InteractionRule(ingredient_a="calcium", ingredient_b="iron",
                           reason="흡수 저해 가능", evidence_id=ev.id))
    db.add(Analysis(trigger="manual", result='{"summary": "ok"}'))
    db.commit()

    assert db.query(NutrientLimit).one().evidence_id == ev.id
    assert db.query(InteractionRule).one().ingredient_b == "iron"
    assert db.query(Analysis).one().trigger == "manual"
```

- [ ] **Step 2: Run test, verify it fails**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/test_models.py -v
```
Expected: FAIL — `ImportError: cannot import name 'EvidenceRef'`.

- [ ] **Step 3: Add the models**

Append to `backend/app/models.py` (no new imports needed — `Boolean, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint` and `Mapped, mapped_column, relationship` are already imported):
```python
class EvidenceRef(Base):
    __tablename__ = "evidence_refs"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String)             # KDRI | NIH_ODS | UL | interaction_rule
    nutrient_code: Mapped[str] = mapped_column(String)
    claim_summary: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String, default="")
    reliability_grade: Mapped[str] = mapped_column(String)  # A | B | C


class NutrientLimit(Base):
    __tablename__ = "nutrient_limits"
    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_code: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String)
    rda: Mapped[float | None] = mapped_column(Float)
    ul: Mapped[float | None] = mapped_column(Float)
    sex: Mapped[str] = mapped_column(String, default="ALL")  # ALL | M | F
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_refs.id"))


class InteractionRule(Base):
    __tablename__ = "interaction_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_a: Mapped[str] = mapped_column(String)
    ingredient_b: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_refs.id"))


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    trigger: Mapped[str] = mapped_column(String)  # manual | weekly
    result: Mapped[str] = mapped_column(Text)     # JSON — see analysis.AnalysisResult
```

- [ ] **Step 4: Run test, verify it passes**

```powershell
.venv\Scripts\python -m pytest tests/test_models.py -v
```
Expected: all pass.

- [ ] **Step 5: Write failing seed test**

Create `backend/tests/test_evidence_seed.py`:
```python
def test_seed_evidence_and_limits(db_session_factory):
    from app.models import EvidenceRef, InteractionRule, NutrientLimit
    from app.seed import seed_evidence_and_limits

    db = db_session_factory()
    seed_evidence_and_limits(db)

    assert db.query(EvidenceRef).count() > 0

    limits = db.query(NutrientLimit).filter_by(ingredient_code="vitamin_d").all()
    assert len(limits) == 1
    assert limits[0].ul == 100
    assert limits[0].evidence_id is not None

    rules = db.query(InteractionRule).all()
    assert any(r.ingredient_a == "calcium" and r.ingredient_b == "iron" for r in rules)


def test_seed_evidence_and_limits_idempotent(db_session_factory):
    from app import seed
    from app.models import EvidenceRef

    db = db_session_factory()
    seed.seed_evidence_and_limits(db)
    seed.seed_evidence_and_limits(db)

    assert db.query(EvidenceRef).count() == len(seed.EVIDENCE_REFS)
```

- [ ] **Step 6: Run test, verify it fails**

```powershell
.venv\Scripts\python -m pytest tests/test_evidence_seed.py -v
```
Expected: FAIL — `ImportError: cannot import name 'seed_evidence_and_limits'`.

- [ ] **Step 7: Implement the seed**

Change the import line at the top of `backend/app/seed.py` from `from .models import MetricDefinition` to:
```python
from .models import EvidenceRef, InteractionRule, MetricDefinition, NutrientLimit
```

Append to `backend/app/seed.py`:
```python
# ponytail: values below are standard adult (19-64) DRI figures included for
# structural completeness. Verify each row against the official KDRIs 2020
# tables before relying on them for real dosing decisions — this seed is a
# starting skeleton, not a certified dataset.
EVIDENCE_REFS = [
    # (type, nutrient_code, claim_summary, source_url, reliability_grade)
    ("KDRI", "vitamin_a", "비타민A 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "vitamin_b6", "비타민B6 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "vitamin_b12", "비타민B12 권장 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "vitamin_c", "비타민C 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "vitamin_d", "비타민D 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "vitamin_e", "비타민E 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "folate", "엽산 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "niacin", "나이아신 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "calcium", "칼슘 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "magnesium", "마그네슘 상한 섭취량(보충제 기준) (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "zinc", "아연 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "iron", "철분 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "selenium", "셀레늄 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("NIH_ODS", "potassium", "칼륨 권장 섭취량 (NIH ODS)", "https://ods.od.nih.gov", "A"),
    ("NIH_ODS", "omega3", "오메가3 적정 섭취량 (NIH ODS)", "https://ods.od.nih.gov", "B"),
    ("interaction_rule", "calcium", "칼슘-철분 동시 복용 시 철분 흡수 저해", "https://ods.od.nih.gov", "B"),
    ("interaction_rule", "omega3", "비타민E-오메가3 고용량 병용 시 출혈 위험 증가", "https://ods.od.nih.gov", "C"),
]

NUTRIENT_LIMITS = [
    # (ingredient_code, unit, rda, ul, sex, evidence_nutrient_code)
    ("vitamin_a", "ug", 800, 3000, "M", "vitamin_a"),
    ("vitamin_a", "ug", 650, 3000, "F", "vitamin_a"),
    ("vitamin_b6", "mg", 1.5, 100, "ALL", "vitamin_b6"),
    ("vitamin_b12", "ug", 2.4, None, "ALL", "vitamin_b12"),
    ("vitamin_c", "mg", 100, 2000, "ALL", "vitamin_c"),
    ("vitamin_d", "ug", 10, 100, "ALL", "vitamin_d"),
    ("vitamin_e", "mg", 12, 540, "ALL", "vitamin_e"),
    ("folate", "ug", 400, 1000, "ALL", "folate"),
    ("niacin", "mg", 16, 35, "M", "niacin"),
    ("niacin", "mg", 14, 35, "F", "niacin"),
    ("calcium", "mg", 800, 2500, "M", "calcium"),
    ("calcium", "mg", 700, 2500, "F", "calcium"),
    ("magnesium", "mg", 340, 350, "M", "magnesium"),
    ("magnesium", "mg", 280, 350, "F", "magnesium"),
    ("zinc", "mg", 10, 35, "M", "zinc"),
    ("zinc", "mg", 8, 35, "F", "zinc"),
    ("iron", "mg", 10, 45, "M", "iron"),
    ("iron", "mg", 14, 45, "F", "iron"),
    ("selenium", "ug", 60, 400, "ALL", "selenium"),
    ("potassium", "mg", 3500, None, "ALL", "potassium"),
    ("omega3", "g", 1.3, None, "ALL", "omega3"),
]

INTERACTION_RULES = [
    # (ingredient_a, ingredient_b, reason, evidence_nutrient_code)
    ("calcium", "iron", "칼슘과 철분을 함께 복용하면 철분 흡수가 저해될 수 있어요. "
                        "2시간 이상 간격을 두고 복용하세요.", "calcium"),
    ("vitamin_e", "omega3", "비타민E와 오메가3를 고용량으로 함께 복용하면 출혈 위험이 "
                           "증가할 수 있어요. 항응고제 복용 중이면 의사와 상의하세요.", "omega3"),
]


def seed_evidence_and_limits(db: Session) -> None:
    if db.query(EvidenceRef).count() > 0:
        return  # static seed set — whole-function idempotency is enough here

    by_nutrient: dict[str, int] = {}
    for type_, nutrient_code, claim, url, grade in EVIDENCE_REFS:
        ev = EvidenceRef(type=type_, nutrient_code=nutrient_code,
                         claim_summary=claim, source_url=url,
                         reliability_grade=grade)
        db.add(ev)
        db.flush()
        by_nutrient.setdefault(nutrient_code, ev.id)

    for code, unit, rda, ul, sex, ev_code in NUTRIENT_LIMITS:
        db.add(NutrientLimit(ingredient_code=code, unit=unit, rda=rda, ul=ul,
                             sex=sex, evidence_id=by_nutrient.get(ev_code)))

    for a, b, reason, ev_code in INTERACTION_RULES:
        db.add(InteractionRule(ingredient_a=a, ingredient_b=b, reason=reason,
                               evidence_id=by_nutrient.get(ev_code)))
    db.commit()
```

- [ ] **Step 8: Wire seeding into app startup**

In `backend/app/main.py`, inside `lifespan()`, after the existing `seed_metric_definitions(db)` call and before `db.close()`:
```python
    from .db import SessionLocal
    from .seed import seed_evidence_and_limits, seed_metric_definitions
    db = SessionLocal()
    try:
        seed_metric_definitions(db)
        seed_evidence_and_limits(db)
    finally:
        db.close()
```
(This replaces the existing two-line import + single seed call with the same block plus the new import and call.)

- [ ] **Step 9: Run full suite, verify pass**

```powershell
.venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 10: Commit**

```powershell
git add -A
git commit -m "feat: add evidence/nutrient-limit/interaction-rule/analysis models and curated seed"
```

---

### Task 2: Safety engine (duplication, overdose, interaction warnings)

**Files:**
- Create: `backend/app/routers/safety.py`
- Modify: `backend/app/main.py` (include router)
- Create: `backend/tests/test_safety.py`

**Interfaces:**
- Consumes: `Supplement` (with `.ingredients`, `.schedules` loaded), `NutrientLimit`, `InteractionRule`, `Profile` from `app.models`.
- Produces: `compute_safety_warnings(supplements, limits, interactions, sex) -> list[dict]` — pure function, warning dicts shaped `{"type": "duplication"|"overdose"|"interaction", "ingredient_code"?: str, "ingredient_codes"?: [str, str], "message": str, ...}`. `GET /api/safety/warnings` → same list, computed live from active supplements + `profile.sex`. Task 4 (analysis engine) does **not** call this — the safety engine and the LLM analysis are deliberately independent per spec §4.3/§4.4 ("AI may explain a warning conversationally but never computes or overrides it"). Dashboard (Task 6) calls this endpoint directly.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_safety.py`:
```python
def _make_supplement(db, product_name, ingredient_code, amount, unit, days="0123456"):
    from app.models import Supplement, SupplementIngredient, SupplementSchedule
    s = Supplement(product_name=product_name)
    s.ingredients.append(SupplementIngredient(
        ingredient_code=ingredient_code, amount=amount, unit=unit))
    s.schedules.append(SupplementSchedule(
        days_of_week=days, time_of_day="09:00", servings=1))
    db.add(s)
    db.commit()
    return s


def test_worst_day_servings_sums_same_day_schedules():
    from app.routers.safety import _worst_day_servings

    class FakeSchedule:
        def __init__(self, days, servings):
            self.days_of_week, self.servings = days, servings

    schedules = [FakeSchedule("0", 1), FakeSchedule("0", 1), FakeSchedule("3", 2)]
    assert _worst_day_servings(schedules) == 2  # Mon: 1+1=2, Thu: 2 -> max is 2


def test_duplication_detected(db_session_factory):
    from app.routers.safety import compute_safety_warnings
    db = db_session_factory()
    s1 = _make_supplement(db, "A", "vitamin_c", 500, "mg")
    s2 = _make_supplement(db, "B", "vitamin_c", 500, "mg")

    warnings = compute_safety_warnings([s1, s2], [], [], "F")
    assert {"type": "duplication", "ingredient_code": "vitamin_c",
           "message": "vitamin_c 성분이 2개 제품에 중복되어 있습니다"} in warnings


def test_overdose_detected_at_or_above_ul(db_session_factory):
    from app.models import NutrientLimit
    from app.routers.safety import compute_safety_warnings
    db = db_session_factory()
    s1 = _make_supplement(db, "고용량C", "vitamin_c", 1500, "mg")
    lim = NutrientLimit(ingredient_code="vitamin_c", unit="mg", rda=100, ul=2000, sex="ALL")
    db.add(lim)
    db.commit()

    warnings = compute_safety_warnings([s1], [lim], [], "F")
    assert any(w["type"] == "overdose" and w["ingredient_code"] == "vitamin_c"
              for w in warnings)


def test_no_overdose_under_ul(db_session_factory):
    from app.models import NutrientLimit
    from app.routers.safety import compute_safety_warnings
    db = db_session_factory()
    s1 = _make_supplement(db, "저용량C", "vitamin_c", 100, "mg")
    lim = NutrientLimit(ingredient_code="vitamin_c", unit="mg", rda=100, ul=2000, sex="ALL")
    db.add(lim)
    db.commit()

    warnings = compute_safety_warnings([s1], [lim], [], "F")
    assert not any(w["type"] == "overdose" for w in warnings)


def test_sex_specific_limit_overrides_all(db_session_factory):
    from app.models import NutrientLimit
    from app.routers.safety import compute_safety_warnings
    db = db_session_factory()
    s1 = _make_supplement(db, "철분", "iron", 40, "mg")
    lim_all = NutrientLimit(ingredient_code="iron", unit="mg", rda=10, ul=45, sex="ALL")
    lim_f = NutrientLimit(ingredient_code="iron", unit="mg", rda=14, ul=45, sex="F")
    db.add_all([lim_all, lim_f])
    db.commit()

    warnings = compute_safety_warnings([s1], [lim_all, lim_f], [], "F")
    assert not any(w["type"] == "overdose" for w in warnings)  # 40mg < 45mg UL


def test_interaction_flagged_when_both_present(db_session_factory):
    from app.models import InteractionRule
    from app.routers.safety import compute_safety_warnings
    db = db_session_factory()
    s1 = _make_supplement(db, "칼슘제", "calcium", 500, "mg")
    s2 = _make_supplement(db, "철분제", "iron", 20, "mg")
    rule = InteractionRule(ingredient_a="calcium", ingredient_b="iron", reason="흡수 저해")
    db.add(rule)
    db.commit()

    warnings = compute_safety_warnings([s1, s2], [], [rule], "F")
    assert {"type": "interaction", "ingredient_codes": ["calcium", "iron"],
           "message": "흡수 저해"} in warnings


def test_safety_endpoint_requires_auth(client):
    assert client.get("/api/safety/warnings").status_code == 401


def test_safety_endpoint_returns_warnings(auth_client, db_session_factory):
    from app.models import Profile
    db = db_session_factory()
    db.add(Profile(id=1, sex="F"))
    _make_supplement(db, "A", "vitamin_c", 500, "mg")
    _make_supplement(db, "B", "vitamin_c", 500, "mg")

    res = auth_client.get("/api/safety/warnings")
    assert res.status_code == 200
    assert any(w["type"] == "duplication" for w in res.json())
```

- [ ] **Step 2: Run tests, verify fail**

```powershell
.venv\Scripts\python -m pytest tests/test_safety.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.routers.safety'`.

- [ ] **Step 3: Implement the safety engine + endpoint**

Create `backend/app/routers/safety.py`:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from ..auth import require_auth
from ..db import get_db
from ..models import InteractionRule, NutrientLimit, Profile, Supplement

router = APIRouter(prefix="/api/safety", tags=["safety"],
                   dependencies=[Depends(require_auth)])


def _worst_day_servings(schedules) -> float:
    totals = [0.0] * 7
    for sch in schedules:
        for d in sch.days_of_week:
            totals[int(d)] += sch.servings
    return max(totals) if totals else 0.0


def compute_safety_warnings(supplements, limits, interactions, sex: str | None) -> list[dict]:
    totals: dict[str, float] = {}
    product_ids: dict[str, set[int]] = {}

    for supp in supplements:
        daily_servings = _worst_day_servings(supp.schedules)
        for ing in supp.ingredients:
            totals[ing.ingredient_code] = totals.get(ing.ingredient_code, 0.0) + ing.amount * daily_servings
            product_ids.setdefault(ing.ingredient_code, set()).add(supp.id)

    warnings: list[dict] = []
    for code, ids in product_ids.items():
        if len(ids) >= 2:
            warnings.append({"type": "duplication", "ingredient_code": code,
                             "message": f"{code} 성분이 {len(ids)}개 제품에 중복되어 있습니다"})

    limit_by_code: dict[str, NutrientLimit] = {}
    for lim in limits:
        if lim.sex not in ("ALL", sex):
            continue
        current = limit_by_code.get(lim.ingredient_code)
        if current is None or (current.sex == "ALL" and lim.sex != "ALL"):
            limit_by_code[lim.ingredient_code] = lim

    for code, total in totals.items():
        lim = limit_by_code.get(code)
        if lim and lim.ul is not None and total >= lim.ul:
            warnings.append({"type": "overdose", "ingredient_code": code,
                             "message": f"{code} 합계 {total}{lim.unit}가 상한섭취량 "
                                       f"{lim.ul}{lim.unit}을 초과합니다",
                             "total": total, "ul": lim.ul, "unit": lim.unit})

    present = set(totals)
    for rule in interactions:
        if rule.ingredient_a in present and rule.ingredient_b in present:
            warnings.append({"type": "interaction",
                             "ingredient_codes": [rule.ingredient_a, rule.ingredient_b],
                             "message": rule.reason})
    return warnings


@router.get("/warnings")
def get_warnings(db: Session = Depends(get_db)):
    supplements = (db.query(Supplement).filter(Supplement.active.is_(True))
                  .options(joinedload(Supplement.ingredients),
                          joinedload(Supplement.schedules)).all())
    limits = db.query(NutrientLimit).all()
    interactions = db.query(InteractionRule).all()
    profile = db.get(Profile, 1)
    return compute_safety_warnings(supplements, limits, interactions,
                                   profile.sex if profile else None)
```

In `backend/app/main.py`, change `from .routers import calendar, meals, metrics, supplements` to:
```python
    from .routers import calendar, meals, metrics, safety, supplements
```
and add after the existing `app.include_router(calendar.router)` line:
```python
    app.include_router(safety.router)
```

- [ ] **Step 4: Run tests, verify pass**

```powershell
.venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: add deterministic safety engine and warnings endpoint"
```

---

### Task 3: Analysis input assembly (deterministic aggregation)

**Files:**
- Create: `backend/app/analysis.py`
- Modify: `backend/app/routers/metrics.py` (extract `latest_metrics_dict` for reuse)
- Create: `backend/tests/test_analysis_input.py`

**Interfaces:**
- Consumes: `latest_metrics_dict(db)` from `app.routers.metrics`; `expand_schedules(schedules, logs, start, end)` from `app.routers.calendar`; `NUTRIENT_KEYS` from `app.nutrition`; `IntakeLog, Meal, MealItem, MetricDefinition, Profile, Supplement` from `app.models`.
- Produces: `build_analysis_input(db: Session) -> dict` with keys `profile` (`{sex, birth_date}`), `latest_metrics` (same shape as `GET /api/metrics/latest`), `nutrient_totals_7d`, `nutrient_totals_30d` (dicts keyed by `NUTRIENT_KEYS`), `supplement_adherence` (`[{supplement_id, product_name, expected, taken}]`), `active_symptoms` (`[{code, name_ko, value_num}]`), `frequent_ingredients` (`[str]`, most-logged meal-item names). Task 4 passes this dict straight into the LLM prompt as JSON — every value must already be JSON-serializable (dates/datetimes are pre-formatted as ISO strings).

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_analysis_input.py`:
```python
import json
from datetime import date, datetime


def test_supplement_adherence_counts(db_session_factory):
    from app.analysis import _supplement_adherence
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

    rows = _supplement_adherence(db, date(2026, 7, 27), date(2026, 8, 2))
    assert rows == [{"supplement_id": s.id, "product_name": "비타민D",
                     "expected": 2, "taken": 1}]


def test_build_analysis_input(db_session_factory):
    from app.analysis import build_analysis_input
    from app.models import (IntakeLog, Meal, MealItem, MetricDefinition,
                            MetricEntry, Profile, Supplement, SupplementSchedule)
    db = db_session_factory()

    db.add(Profile(id=1, sex="F", birth_date=date(1990, 6, 25)))
    db.add(MetricDefinition(code="fatigue", name_ko="피로감", unit="", domain="symptom",
                            input_type="scale", range_low=0, range_high=3))
    db.add(MetricEntry(metric_code="fatigue", value_num=2, measured_at=datetime.now()))

    meal = Meal(eaten_at=datetime.now(), dish_name="김치찌개")
    meal.items.append(MealItem(name="돼지고기", amount="100g",
                               nutrients=json.dumps({"kcal": 100, "protein_g": 20}),
                               nutrient_source="mfds_db"))
    db.add(meal)

    supp = Supplement(product_name="비타민D")
    supp.schedules.append(SupplementSchedule(days_of_week="0123456",
                                             time_of_day="09:00", servings=1))
    db.add(supp)
    db.commit()
    db.add(IntakeLog(schedule_id=supp.schedules[0].id, date=date.today(), status="taken"))
    db.commit()

    data = build_analysis_input(db)

    assert data["profile"] == {"sex": "F", "birth_date": "1990-06-25"}
    assert data["nutrient_totals_7d"]["kcal"] == 100
    assert data["nutrient_totals_30d"]["kcal"] == 100
    assert data["active_symptoms"] == [{"code": "fatigue", "name_ko": "피로감", "value_num": 2}]
    assert data["frequent_ingredients"] == ["돼지고기"]
    supp_row = data["supplement_adherence"][0]
    assert supp_row["taken"] == 1
    assert supp_row["expected"] >= 1
    json.dumps(data)  # must be JSON-serializable end to end
```

- [ ] **Step 2: Run tests, verify fail**

```powershell
.venv\Scripts\python -m pytest tests/test_analysis_input.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.analysis'`.

- [ ] **Step 3: Extract `latest_metrics_dict` in metrics router**

In `backend/app/routers/metrics.py`, replace:
```python
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
```
with:
```python
def latest_metrics_dict(db: Session) -> dict:
    entries = (db.query(MetricEntry)
               .order_by(MetricEntry.measured_at.asc()).all())
    out: dict[str, dict] = {}
    for e in entries:  # ascending — last write per code wins
        out[e.metric_code] = {"value_num": e.value_num,
                              "value_text": e.value_text,
                              "measured_at": e.measured_at.isoformat()}
    return out


@router.get("/latest")
def latest_per_metric(db: Session = Depends(get_db)):
    return latest_metrics_dict(db)
```

- [ ] **Step 4: Implement `app/analysis.py`**

Create `backend/app/analysis.py`:
```python
import json
from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from .models import (IntakeLog, Meal, MealItem, MetricDefinition, Profile,
                     Supplement)
from .nutrition import NUTRIENT_KEYS
from .routers.calendar import expand_schedules
from .routers.metrics import latest_metrics_dict


def _sum_nutrients(items: list[MealItem]) -> dict:
    totals = {k: 0.0 for k in NUTRIENT_KEYS}
    for it in items:
        if not it.nutrients:
            continue
        values = json.loads(it.nutrients)
        for k in NUTRIENT_KEYS:
            v = values.get(k)
            if v is not None:
                totals[k] += v
    return {k: round(v, 2) for k, v in totals.items()}


def _nutrient_totals_since(db: Session, since: datetime) -> dict:
    items = db.query(MealItem).join(Meal).filter(Meal.eaten_at >= since).all()
    return _sum_nutrients(items)


def _supplement_adherence(db: Session, start: date, end: date) -> list[dict]:
    supps = (db.query(Supplement).filter(Supplement.active.is_(True))
             .options(joinedload(Supplement.schedules)).all())
    schedules = [s for supp in supps for s in supp.schedules]
    logs = db.query(IntakeLog).filter(IntakeLog.date >= start, IntakeLog.date <= end).all()
    slots = expand_schedules(schedules, logs, start, end)

    by_supp: dict[int, dict] = {
        supp.id: {"supplement_id": supp.id, "product_name": supp.product_name,
                 "expected": 0, "taken": 0}
        for supp in supps
    }
    for slot in slots:
        row = by_supp.get(slot["supplement_id"])
        if row is None:
            continue
        row["expected"] += 1
        if slot["status"] == "taken":
            row["taken"] += 1
    return list(by_supp.values())


def _active_symptoms(db: Session, latest: dict) -> list[dict]:
    defs = {d.code: d for d in db.query(MetricDefinition)
            .filter(MetricDefinition.domain == "symptom").all()}
    out = []
    for code, entry in latest.items():
        d = defs.get(code)
        if d and d.input_type == "scale" and (entry["value_num"] or 0) >= 1:
            out.append({"code": code, "name_ko": d.name_ko, "value_num": entry["value_num"]})
    return out


def _frequent_ingredients(db: Session, since: datetime, limit: int = 8) -> list[str]:
    rows = db.query(MealItem.name).join(Meal).filter(Meal.eaten_at >= since).all()
    counts = Counter(name for (name,) in rows)
    return [name for name, _ in counts.most_common(limit)]


def build_analysis_input(db: Session) -> dict:
    now = datetime.now()
    today = now.date()
    profile = db.get(Profile, 1)
    latest = latest_metrics_dict(db)
    return {
        "profile": {"sex": profile.sex if profile else None,
                    "birth_date": profile.birth_date.isoformat()
                    if profile and profile.birth_date else None},
        "latest_metrics": latest,
        "nutrient_totals_7d": _nutrient_totals_since(db, now - timedelta(days=7)),
        "nutrient_totals_30d": _nutrient_totals_since(db, now - timedelta(days=30)),
        "supplement_adherence": _supplement_adherence(db, today - timedelta(days=29), today),
        "active_symptoms": _active_symptoms(db, latest),
        "frequent_ingredients": _frequent_ingredients(db, now - timedelta(days=90)),
    }
```

- [ ] **Step 5: Run tests, verify pass**

```powershell
.venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass (this also re-runs `test_metrics.py::test_entry_roundtrip_and_latest` against the refactored `/latest` route — confirms the extraction didn't change behavior).

- [ ] **Step 6: Commit**

```powershell
git add -A
git commit -m "feat: add deterministic analysis input assembly"
```

---

### Task 4: Analysis engine (LLM call, schema validation, storage, API)

**Files:**
- Modify: `backend/app/config.py` (add `openai_model_strong`)
- Modify: `backend/app/analysis.py` (append LLM engine)
- Create: `backend/app/routers/analysis.py`
- Modify: `backend/app/main.py` (include router)
- Create: `backend/tests/test_analysis.py`

**Interfaces:**
- Consumes: `build_analysis_input(db)` from Task 3; `EvidenceRef`, `NutrientLimit`, `Analysis` models; `settings.openai_model_strong`, `settings.openai_api_key`.
- Produces: `AnalysisResult` (Pydantic model — `summary: str`, `deficiencies/excesses: list[NutrientNote]`, `top3: list[Top3Entry]` (max 3, each ≥3 actions), `missing_data: list[MissingDataItem]`); `AnalysisError(Exception)`; `run_analysis(db: Session, trigger: str) -> Analysis` (retries once on any failure — bad JSON, schema violation, unresolvable `evidence_ids`, network error — then raises `AnalysisError`). `POST /api/analysis/run` → 201 with the stored result or 502 on `AnalysisError`; `GET /api/analysis/latest` → latest result or `null`; `GET /api/analysis` → `[{id, run_at, trigger, summary}]`; `GET /api/analysis/{id}` → full result or 404. Task 6 (dashboard) and Task 5 (report page) consume these three GET shapes directly.

- [ ] **Step 1: Write failing engine tests**

Create `backend/tests/test_analysis.py`:
```python
import json
from datetime import datetime


GOOD_RESULT = {
    "summary": "전반적으로 양호합니다",
    "deficiencies": [{"nutrient": "vitamin_d", "confidence": "med", "evidence_ids": [1]}],
    "excesses": [],
    "top3": [{
        "nutrient": "vitamin_d", "why": "일조량 부족",
        "actions": [
            {"type": "food", "text": "고등어", "portion": "100g"},
            {"type": "recipe", "text": "고등어구이"},
            {"type": "habit", "text": "산책 30분"},
        ],
        "evidence_ids": [1],
    }],
    "missing_data": [{"metric_code": "vitamin_d", "why_it_matters": "혈중 농도 확인 필요"}],
}


def _fake_client(payload_sequence):
    calls = {"n": 0}

    class FakeMsg:
        def __init__(self, content): self.content = content

    class FakeChoice:
        def __init__(self, content): self.message = FakeMsg(content)

    class FakeCompletion:
        def __init__(self, content): self.choices = [FakeChoice(content)]

    class FakeCompletions:
        def create(self, **kw):
            payload = payload_sequence[min(calls["n"], len(payload_sequence) - 1)]
            calls["n"] += 1
            return FakeCompletion(json.dumps(payload))

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kw): self.chat = FakeChat()

    return FakeClient


def _seed_evidence(db_session_factory):
    from app.models import EvidenceRef
    db = db_session_factory()
    db.add(EvidenceRef(id=1, type="KDRI", nutrient_code="vitamin_d",
                       claim_summary="비타민D 권장량", source_url="https://www.mohw.go.kr",
                       reliability_grade="A"))
    db.commit()
    return db


def test_run_analysis_success(db_session_factory, monkeypatch):
    from app import analysis
    db = _seed_evidence(db_session_factory)
    monkeypatch.setattr(analysis, "OpenAI", _fake_client([GOOD_RESULT]))
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    result = analysis.run_analysis(db, trigger="manual")
    stored = json.loads(result.result)
    assert stored["summary"] == "전반적으로 양호합니다"
    assert result.trigger == "manual"


def test_run_analysis_retries_on_bad_citation(db_session_factory, monkeypatch):
    from app import analysis
    db = _seed_evidence(db_session_factory)
    bad = {**GOOD_RESULT, "top3": [{**GOOD_RESULT["top3"][0], "evidence_ids": [999]}]}
    monkeypatch.setattr(analysis, "OpenAI", _fake_client([bad, GOOD_RESULT]))
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    result = analysis.run_analysis(db, trigger="manual")
    stored = json.loads(result.result)
    assert stored["top3"][0]["evidence_ids"] == [1]


def test_run_analysis_fails_after_two_bad_attempts(db_session_factory, monkeypatch):
    from app import analysis
    db = _seed_evidence(db_session_factory)
    bad = {**GOOD_RESULT, "top3": [{**GOOD_RESULT["top3"][0], "evidence_ids": [999]}]}
    monkeypatch.setattr(analysis, "OpenAI", _fake_client([bad, bad]))
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    try:
        analysis.run_analysis(db, trigger="manual")
        assert False, "expected AnalysisError"
    except analysis.AnalysisError:
        pass


def test_run_analysis_network_failure(db_session_factory, monkeypatch):
    from app import analysis
    db = _seed_evidence(db_session_factory)

    class BoomCompletions:
        def create(self, **kw):
            raise RuntimeError("network down")

    class BoomChat:
        completions = BoomCompletions()

    class BoomClient:
        def __init__(self, **kw): self.chat = BoomChat()

    monkeypatch.setattr(analysis, "OpenAI", BoomClient)
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    try:
        analysis.run_analysis(db, trigger="manual")
        assert False, "expected AnalysisError"
    except analysis.AnalysisError:
        pass


def test_run_endpoint(auth_client, db_session_factory, monkeypatch):
    from app import analysis
    _seed_evidence(db_session_factory)
    monkeypatch.setattr(analysis, "OpenAI", _fake_client([GOOD_RESULT]))
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    res = auth_client.post("/api/analysis/run")
    assert res.status_code == 201
    assert res.json()["summary"] == "전반적으로 양호합니다"


def test_run_endpoint_failure_returns_502(auth_client, db_session_factory, monkeypatch):
    from app import analysis
    _seed_evidence(db_session_factory)
    bad = {**GOOD_RESULT, "top3": [{**GOOD_RESULT["top3"][0], "evidence_ids": [999]}]}
    monkeypatch.setattr(analysis, "OpenAI", _fake_client([bad, bad]))
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    res = auth_client.post("/api/analysis/run")
    assert res.status_code == 502


def test_analysis_list_and_get(auth_client, db_session_factory):
    from app.models import Analysis
    db = db_session_factory()
    db.add(Analysis(trigger="manual", result=json.dumps(GOOD_RESULT),
                    run_at=datetime(2026, 7, 29, 9, 0)))
    db.commit()

    latest = auth_client.get("/api/analysis/latest").json()
    assert latest["summary"] == "전반적으로 양호합니다"

    listing = auth_client.get("/api/analysis").json()
    assert len(listing) == 1 and listing[0]["trigger"] == "manual"

    detail = auth_client.get(f"/api/analysis/{listing[0]['id']}").json()
    assert detail["top3"][0]["nutrient"] == "vitamin_d"

    assert auth_client.get("/api/analysis/9999").status_code == 404


def test_analysis_latest_is_null_when_none_exist(auth_client):
    assert auth_client.get("/api/analysis/latest").json() is None


def test_analysis_requires_auth(client):
    assert client.get("/api/analysis").status_code == 401
```

- [ ] **Step 2: Run tests, verify fail**

```powershell
.venv\Scripts\python -m pytest tests/test_analysis.py -v
```
Expected: FAIL — `run_analysis`/`OpenAI` not defined on `app.analysis`, and `/api/analysis/*` 404.

- [ ] **Step 3: Add the strong-model setting**

In `backend/app/config.py`, add a field to `Settings` right after `openai_model_mini`:
```python
    openai_model_strong: str = "gpt-5"
```

- [ ] **Step 4: Append the LLM engine to `app/analysis.py`**

Append to `backend/app/analysis.py`:
```python
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, field_validator

from .config import settings
from .models import Analysis, EvidenceRef, NutrientLimit


class AnalysisError(Exception):
    pass


class ActionOut(BaseModel):
    type: Literal["food", "recipe", "habit"]
    text: str
    portion: str | None = None
    uses_frequent_ingredients: bool | None = None


class Top3Entry(BaseModel):
    nutrient: str
    why: str
    actions: list[ActionOut]
    evidence_ids: list[int]

    @field_validator("actions")
    @classmethod
    def _min_actions(cls, v: list[ActionOut]) -> list[ActionOut]:
        if len(v) < 3:
            raise ValueError("top3 entries need at least 3 actions")
        return v


class NutrientNote(BaseModel):
    nutrient: str
    confidence: Literal["high", "med", "low"]
    evidence_ids: list[int]


class MissingDataItem(BaseModel):
    metric_code: str
    why_it_matters: str


class AnalysisResult(BaseModel):
    summary: str
    deficiencies: list[NutrientNote] = []
    excesses: list[NutrientNote] = []
    top3: list[Top3Entry]
    missing_data: list[MissingDataItem] = []

    @field_validator("top3")
    @classmethod
    def _max_three(cls, v: list[Top3Entry]) -> list[Top3Entry]:
        if len(v) > 3:
            raise ValueError("top3 must have at most 3 entries")
        return v


def _all_evidence_ids(result: AnalysisResult) -> set[int]:
    ids: set[int] = set()
    for note in (*result.deficiencies, *result.excesses):
        ids.update(note.evidence_ids)
    for entry in result.top3:
        ids.update(entry.evidence_ids)
    return ids


def _validate_citations(result: AnalysisResult, valid_ids: set[int]) -> None:
    unknown = _all_evidence_ids(result) - valid_ids
    if unknown:
        raise ValueError(f"근거 없는 evidence_id: {sorted(unknown)}")


_SCHEMA_HINT = (
    '{"summary": str, '
    '"deficiencies": [{"nutrient": str, "confidence": "high|med|low", "evidence_ids": [int]}], '
    '"excesses": [...동일 구조...], '
    '"top3": [{"nutrient": str, "why": str, '
    '"actions": [{"type": "food|recipe|habit", "text": str, "portion"?: str, '
    '"uses_frequent_ingredients"?: bool}] (최소 3개), '
    '"evidence_ids": [int]}] (최대 3개), '
    '"missing_data": [{"metric_code": str, "why_it_matters": str}]}'
)


def _call_llm(input_data: dict, evidence: list[dict], limits: list[dict],
             retry_hint: str | None) -> dict:
    client = OpenAI(api_key=settings.openai_api_key)
    prompt = (
        "당신은 건강 데이터 분석 도우미입니다. 아래 데이터를 바탕으로 지정된 "
        "스키마의 JSON으로만 답하세요. evidence_ids는 반드시 아래 '참고 근거' "
        "목록에 있는 id만 사용하세요.\n"
        f"데이터: {json.dumps(input_data, ensure_ascii=False)}\n"
        f"참고 근거: {json.dumps(evidence, ensure_ascii=False)}\n"
        f"영양소 권장섭취량 참고: {json.dumps(limits, ensure_ascii=False)}\n"
        f"스키마: {_SCHEMA_HINT}"
    )
    if retry_hint:
        prompt += f"\n이전 시도 오류(반드시 수정): {retry_hint}"
    res = client.chat.completions.create(
        model=settings.openai_model_strong,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(res.choices[0].message.content)


def run_analysis(db: Session, trigger: str) -> Analysis:
    input_data = build_analysis_input(db)
    evidence = [{"id": e.id, "nutrient_code": e.nutrient_code,
                "claim_summary": e.claim_summary,
                "reliability_grade": e.reliability_grade}
               for e in db.query(EvidenceRef).all()]
    valid_ids = {e["id"] for e in evidence}
    limits = [{"ingredient_code": lim.ingredient_code, "rda": lim.rda, "unit": lim.unit}
             for lim in db.query(NutrientLimit).all()]

    result: AnalysisResult | None = None
    last_error: str | None = None
    for _ in range(2):
        try:
            raw = _call_llm(input_data, evidence, limits, last_error)
            parsed = AnalysisResult.model_validate(raw)
            _validate_citations(parsed, valid_ids)
            result = parsed
            break
        except Exception as exc:  # bad JSON, schema violation, bad citation, network error
            last_error = str(exc)

    if result is None:
        raise AnalysisError(f"분석 결과 검증에 실패했습니다: {last_error}")

    analysis = Analysis(trigger=trigger, result=result.model_dump_json())
    db.add(analysis)
    db.commit()
    return analysis
```

- [ ] **Step 5: Implement the router**

Create `backend/app/routers/analysis.py`:
```python
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..analysis import AnalysisError, run_analysis
from ..auth import require_auth
from ..db import get_db
from ..models import Analysis

router = APIRouter(prefix="/api/analysis", tags=["analysis"],
                   dependencies=[Depends(require_auth)])


def analysis_to_dict(a: Analysis) -> dict:
    return {"id": a.id, "run_at": a.run_at.isoformat(), "trigger": a.trigger,
           **json.loads(a.result)}


@router.post("/run", status_code=201)
def trigger_analysis(db: Session = Depends(get_db)):
    try:
        analysis = run_analysis(db, trigger="manual")
    except AnalysisError as exc:
        raise HTTPException(502, str(exc))
    return analysis_to_dict(analysis)


@router.get("/latest")
def latest_analysis(db: Session = Depends(get_db)):
    a = db.query(Analysis).order_by(Analysis.run_at.desc()).first()
    return analysis_to_dict(a) if a else None


@router.get("")
def list_analyses(db: Session = Depends(get_db)):
    rows = db.query(Analysis).order_by(Analysis.run_at.desc()).all()
    return [{"id": a.id, "run_at": a.run_at.isoformat(), "trigger": a.trigger,
            "summary": json.loads(a.result)["summary"]} for a in rows]


@router.get("/{analysis_id}")
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    a = db.get(Analysis, analysis_id)
    if a is None:
        raise HTTPException(404, "리포트를 찾을 수 없습니다")
    return analysis_to_dict(a)
```

Note: `/latest` is declared before `/{analysis_id}` — Starlette matches routes in declaration order, so a literal `/api/analysis/latest` request hits the literal route first instead of being captured as `analysis_id="latest"`.

In `backend/app/main.py`, change `from .routers import calendar, meals, metrics, safety, supplements` to:
```python
    from .routers import analysis, calendar, meals, metrics, safety, supplements
```
and add after `app.include_router(safety.router)`:
```python
    app.include_router(analysis.router)
```

- [ ] **Step 6: Run tests, verify pass**

```powershell
.venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add -A
git commit -m "feat: add analysis engine with citation-checked LLM output and API"
```

---

### Task 5: 리포트 (Report) page

**Files:**
- Create: `frontend/src/pages/ReportPage.tsx`
- Modify: `frontend/src/App.tsx` (add route + tab)
- Modify: `frontend/src/App.test.tsx` (add tab-label assertion)

**Interfaces:**
- Consumes: `api<T>()` from `../api`; `GET /api/analysis/latest`, `GET /api/analysis`, `GET /api/analysis/{id}`, `POST /api/analysis/run`.
- Produces: exports `Top3Card` (component), `Top3Entry`, `AnalysisDetail` (types) for reuse by `DashboardPage.tsx` in Task 6.

- [ ] **Step 1: Implement the page**

Create `frontend/src/pages/ReportPage.tsx`:
```tsx
import { useEffect, useState } from "react";
import { api } from "../api";

interface Action {
  type: string; text: string; portion?: string | null;
  uses_frequent_ingredients?: boolean | null;
}
export interface Top3Entry {
  nutrient: string; why: string; actions: Action[]; evidence_ids: number[];
}
interface NutrientNote { nutrient: string; confidence: string; evidence_ids: number[]; }
interface MissingDataItem { metric_code: string; why_it_matters: string; }
export interface AnalysisDetail {
  id: number; run_at: string; trigger: string; summary: string;
  deficiencies: NutrientNote[]; excesses: NutrientNote[];
  top3: Top3Entry[]; missing_data: MissingDataItem[];
}
interface AnalysisListItem { id: number; run_at: string; trigger: string; summary: string; }

const GRADE_LABEL: Record<string, string> = { high: "높음", med: "중간", low: "낮음" };
const ACTION_LABEL: Record<string, string> = { food: "음식", recipe: "레시피", habit: "습관" };

export function Top3Card({ entry }: { entry: Top3Entry }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-4 space-y-2">
      <p className="font-medium">{entry.nutrient}</p>
      <p className="text-sm text-slate-500">{entry.why}</p>
      <ul className="space-y-1">
        {entry.actions.map((a, i) => (
          <li key={i} className="text-sm">
            <span className="text-xs text-sky-600 font-semibold mr-1">
              [{ACTION_LABEL[a.type] ?? a.type}]
            </span>
            {a.text}{a.portion ? ` (${a.portion})` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function ReportPage() {
  const [detail, setDetail] = useState<AnalysisDetail | null>(null);
  const [history, setHistory] = useState<AnalysisListItem[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  function loadLatest() {
    api<AnalysisDetail | null>("/api/analysis/latest").then(setDetail);
  }
  function loadHistory() {
    api<AnalysisListItem[]>("/api/analysis").then(setHistory);
  }
  useEffect(() => { loadLatest(); loadHistory(); }, []);

  async function runAnalysis() {
    setRunning(true);
    setError("");
    try {
      const result = await api<AnalysisDetail>("/api/analysis/run", { method: "POST" });
      setDetail(result);
      loadHistory();
    } catch {
      setError("분석에 실패했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="max-w-lg mx-auto px-4 pt-6 space-y-4">
      <div className="flex items-center">
        <h1 className="text-xl font-bold">리포트</h1>
        <button onClick={runAnalysis} disabled={running}
                className="ml-auto bg-sky-600 text-white rounded-lg px-4 py-2 text-sm disabled:opacity-40">
          {running ? "분석 중..." : "분석하기"}
        </button>
      </div>
      <p className="text-xs text-slate-400">의학적 진단이 아닙니다. 참고용 정보입니다.</p>
      {error && <p className="text-sm text-red-500">{error}</p>}

      {detail ? (
        <>
          <div className="bg-white rounded-xl shadow-sm p-4">
            <p className="text-xs text-slate-400">{detail.run_at.slice(0, 16).replace("T", " ")}</p>
            <p className="mt-1">{detail.summary}</p>
          </div>

          {detail.top3.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-slate-500">부족 영양소 TOP 3</h2>
              {detail.top3.map((e, i) => <Top3Card key={i} entry={e} />)}
            </section>
          )}

          {detail.deficiencies.length > 0 && (
            <section className="bg-white rounded-xl shadow-sm p-4 space-y-1">
              <h2 className="text-sm font-semibold text-slate-500">부족 가능성</h2>
              {detail.deficiencies.map((d, i) => (
                <p key={i} className="text-sm">{d.nutrient} · 신뢰도 {GRADE_LABEL[d.confidence] ?? d.confidence}</p>
              ))}
            </section>
          )}

          {detail.excesses.length > 0 && (
            <section className="bg-white rounded-xl shadow-sm p-4 space-y-1">
              <h2 className="text-sm font-semibold text-slate-500">과다 가능성</h2>
              {detail.excesses.map((d, i) => (
                <p key={i} className="text-sm">{d.nutrient} · 신뢰도 {GRADE_LABEL[d.confidence] ?? d.confidence}</p>
              ))}
            </section>
          )}
        </>
      ) : (
        <p className="text-sm text-slate-400 text-center pt-8">
          아직 분석 기록이 없습니다. 분석하기 버튼을 눌러보세요.
        </p>
      )}

      {history.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-slate-500">지난 리포트</h2>
          {history.map((h) => (
            <button key={h.id}
                    onClick={() => api<AnalysisDetail>(`/api/analysis/${h.id}`).then(setDetail)}
                    className="w-full text-left bg-white rounded-xl shadow-sm p-3">
              <p className="text-xs text-slate-400">{h.run_at.slice(0, 16).replace("T", " ")}</p>
              <p className="text-sm truncate">{h.summary}</p>
            </button>
          ))}
        </section>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire the route and tab**

In `frontend/src/App.tsx`, add the import:
```tsx
import ReportPage from "./pages/ReportPage";
```
Add to the `TABS` array (after the `영양제` entry):
```tsx
  { to: "/report", label: "리포트", icon: "📄" },
```
Add to `<Routes>` (before the `path="*"` route):
```tsx
          <Route path="/report" element={<ReportPage />} />
```

- [ ] **Step 3: Update the smoke test**

In `frontend/src/App.test.tsx`, add a line to `test("renders tab bar", ...)`:
```tsx
  expect(nav.getByText("리포트")).toBeDefined();
```

- [ ] **Step 4: Build + manual QA**

```powershell
cd frontend
npm run build
npm run test
```
Then with both servers running: open 리포트 tab with no analysis yet → see the empty state; click 분석하기 with `OPENAI_API_KEY` unset → see the friendly Korean error message (502 path); with a real key configured, click 분석하기 → summary + up to 3 cards (each with ≥3 labeled actions) render, and the run appears in "지난 리포트"; clicking a past report swaps the detail view without a full reload.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: add report page with on-demand analysis and history"
```

---

### Task 6: 대시보드 (Dashboard) page — new home

**Files:**
- Create: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/App.tsx` (add route + tab, change default redirect)
- Modify: `frontend/src/App.test.tsx` (add tab-label assertion + fetch-stub branches)

**Interfaces:**
- Consumes: `Top3Card`, `Top3Entry`, `AnalysisDetail` from `./ReportPage` (Task 5); `GET /api/analysis/latest`, `GET /api/safety/warnings`, `GET /api/calendar`, `GET /api/metrics/definitions`, `POST /api/intake`, `POST /api/metrics/entries`.
- Produces: default landing route `/dashboard`.

- [ ] **Step 1: Implement the page**

Create `frontend/src/pages/DashboardPage.tsx`:
```tsx
import { useEffect, useState } from "react";
import { api } from "../api";
import { Top3Card, type AnalysisDetail } from "./ReportPage";

interface Warning {
  type: string; ingredient_code?: string; ingredient_codes?: string[]; message: string;
}
interface Slot {
  date: string; time: string; schedule_id: number; supplement_id: number;
  supplement_name: string; servings: number; status: "taken" | "skipped" | "pending";
}
interface MetricDef {
  code: string; name_ko: string; unit: string; domain: string;
  input_type: string; range_low: number | null; range_high: number | null;
}

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const WARNING_STYLE: Record<string, string> = {
  overdose: "bg-red-50 text-red-700 border-red-200",
  duplication: "bg-amber-50 text-amber-700 border-amber-200",
  interaction: "bg-amber-50 text-amber-700 border-amber-200",
};

function MissingDataCard({ item, def, onSaved }: {
  item: { metric_code: string; why_it_matters: string };
  def: MetricDef | undefined;
  onSaved: () => void;
}) {
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);
  if (!def) return null;

  async function save(valueNum: number | null, valueText: string | null) {
    setSaving(true);
    try {
      await api("/api/metrics/entries", {
        method: "POST",
        body: JSON.stringify({ metric_code: def!.code, value_num: valueNum, value_text: valueText }),
      });
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-4 space-y-2">
      <p className="font-medium">{def.name_ko}</p>
      <p className="text-sm text-slate-500">{item.why_it_matters}</p>
      {def.input_type === "scale" ? (
        <div className="flex gap-2">
          {["없음", "가끔", "자주", "심함"].map((label, i) => (
            <button key={i} disabled={saving} onClick={() => save(i, null)}
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
            value={input} onChange={(e) => setInput(e.target.value)}
            placeholder={def.unit || "입력"}
            className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm" />
          <button disabled={saving || !input}
                  onClick={() => def.input_type === "number" ? save(Number(input), null) : save(null, input)}
                  className="bg-sky-600 text-white rounded-lg px-4 text-sm disabled:opacity-40">
            저장
          </button>
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const [detail, setDetail] = useState<AnalysisDetail | null>(null);
  const [warnings, setWarnings] = useState<Warning[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [defs, setDefs] = useState<MetricDef[]>([]);
  const today = iso(new Date());

  function reload() {
    api<AnalysisDetail | null>("/api/analysis/latest").then(setDetail);
    api<Warning[]>("/api/safety/warnings").then(setWarnings);
    api<{ supplement_slots: Slot[] }>(`/api/calendar?start=${today}&end=${today}`)
      .then((d) => setSlots(d.supplement_slots));
  }
  useEffect(() => {
    reload();
    api<MetricDef[]>("/api/metrics/definitions").then(setDefs);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function setIntake(slot: Slot, status: "taken" | "skipped") {
    await api("/api/intake", {
      method: "POST",
      body: JSON.stringify({ schedule_id: slot.schedule_id, date: today, status }),
    });
    reload();
  }

  const defByCode = Object.fromEntries(defs.map((d) => [d.code, d]));

  return (
    <div className="max-w-lg mx-auto px-4 pt-6 space-y-4">
      <h1 className="text-xl font-bold">대시보드</h1>

      {warnings.length > 0 && (
        <section className="space-y-2">
          {warnings.map((w, i) => (
            <div key={i}
                className={`rounded-xl border p-3 text-sm ${WARNING_STYLE[w.type] ?? "bg-slate-50 border-slate-200"}`}>
              {w.message}
            </div>
          ))}
        </section>
      )}

      {slots.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-slate-500">오늘의 영양제</h2>
          {slots.map((s) => (
            <div key={s.schedule_id} className="bg-white rounded-xl shadow-sm p-3 flex items-center gap-2">
              <span className="text-sm">{s.time} · {s.supplement_name}</span>
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
      )}

      {detail ? (
        <>
          <div className="bg-white rounded-xl shadow-sm p-4">
            <p className="text-xs text-slate-400">건강 상태 요약</p>
            <p className="mt-1">{detail.summary}</p>
          </div>
          {detail.top3.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-slate-500">부족 영양소 TOP 3</h2>
              {detail.top3.map((e, i) => <Top3Card key={i} entry={e} />)}
            </section>
          )}
          {detail.missing_data.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-slate-500">추가로 알려주시면 좋아요</h2>
              {detail.missing_data.map((m, i) => (
                <MissingDataCard key={i} item={m} def={defByCode[m.metric_code]} onSaved={reload} />
              ))}
            </section>
          )}
        </>
      ) : (
        <p className="text-sm text-slate-400 text-center pt-8">
          아직 분석 기록이 없습니다. 리포트 탭에서 분석하기를 눌러보세요.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire the route, make it the default tab**

In `frontend/src/App.tsx`:
- Add the import: `import DashboardPage from "./pages/DashboardPage";`
- Prepend to `TABS` (it becomes the first/leftmost tab):
  ```tsx
    { to: "/dashboard", label: "대시보드", icon: "🏠" },
  ```
- Add to `<Routes>` (before `/data`):
  ```tsx
            <Route path="/dashboard" element={<DashboardPage />} />
  ```
- Change the catch-all redirect from `/data` to `/dashboard`:
  ```tsx
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
  ```

- [ ] **Step 3: Update the smoke test**

`DashboardPage` now mounts by default (the `*` redirect lands there), so the fetch stub in `frontend/src/App.test.tsx` needs a body for every endpoint it calls on mount. Replace the `beforeEach` block with:
```tsx
beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const u = url.toString();
      let body = "{}";
      if (u.includes("/api/metrics/definitions")) body = "[]";
      else if (u.includes("/api/analysis/latest")) body = "null";
      else if (u.includes("/api/analysis")) body = "[]";
      else if (u.includes("/api/safety/warnings")) body = "[]";
      else if (u.includes("/api/calendar")) body = '{"meals":[],"supplement_slots":[]}';
      return Promise.resolve(
        new Response(body, { status: 200, headers: { "Content-Type": "application/json" } })
      );
    })
  );
});
```
And add to `test("renders tab bar", ...)`:
```tsx
  expect(nav.getByText("대시보드")).toBeDefined();
```

- [ ] **Step 4: Build + manual QA**

```powershell
npm run build
npm run test
```
Then with both servers running, verify on a phone-width viewport: app opens to 대시보드 by default; with a duplicated supplement, a red/amber warning banner shows immediately; today's supplement checklist shows and tapping 복용 ✓/건너뜀 updates state and matches 캘린더's day view; with a stored analysis, summary + top-3 cards render and a missing-data card saves a value via `/api/metrics/entries` (returns 201, no error). Note: the card list is driven by the last stored analysis, so it does not change on reload until a new analysis is run — that's expected.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: add dashboard as home page with warnings, checklist, and analysis summary"
```

---

## Self-Review Notes

- **Spec coverage:** §8 task 6 (evidence_refs/nutrient_limits/interaction curation) → Task 1. Task 7 (safety engine + warnings UI) → Task 2 (engine) + Task 6 (UI banner). Task 8 (analysis engine, input assembly, LLM call, schema validation, report storage, 리포트 page) → Tasks 3, 4, 5. Task 9 (대시보드: summary, top-3 cards, checklist, warnings, missing-data cards) → Task 6. The weekly-scheduler half of §4.4's trigger list is explicitly deferred to Phase 4 item 13 per the Scope note.
- **Type consistency check:** `AnalysisResult`/`Top3Entry`/`NutrientNote`/`MissingDataItem` (Task 4, Python) and `AnalysisDetail`/`Top3Entry`/`Action` (Task 5, TypeScript) carry matching field names (`summary`, `deficiencies`, `excesses`, `top3`, `missing_data`, `nutrient`, `why`, `actions`, `evidence_ids`, `type`, `text`, `portion`, `uses_frequent_ingredients`, `metric_code`, `why_it_matters`) — the frontend types were written directly from the Pydantic schema, not re-derived independently. `compute_safety_warnings`'s warning shape (`type`, `ingredient_code`, `ingredient_codes`, `message`) matches the `Warning` interface consumed in `DashboardPage.tsx`.
- **No placeholders:** every step above contains complete, runnable code and exact commands; no "TBD"/"similar to Task N" shortcuts.
