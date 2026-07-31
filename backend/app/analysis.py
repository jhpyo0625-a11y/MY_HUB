import json
import logging
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session, joinedload

from .config import settings
from .models import (Analysis, EvidenceRef, IntakeLog, Meal, MealItem,
                     MetricDefinition, NutrientLimit, Profile, Supplement)
from .nutrition import NUTRIENT_KEYS
from .routers.calendar import expand_schedules
from .routers.metrics import latest_metrics_dict

logger = logging.getLogger(__name__)


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
        # Prompt asks for 3; accept 1-3 so a usable report isn't rejected when a
        # (free-tier) model returns fewer — a short report beats a 502.
        if len(v) < 1:
            raise ValueError("top3 entries need at least 1 action")
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
    '"uses_frequent_ingredients"?: bool}] (가능하면 3개, 최소 1개), '
    '"evidence_ids": [int]}] (최대 3개), '
    '"missing_data": [{"metric_code": str, "why_it_matters": str}]}'
)


def _call_llm(input_data: dict, evidence: list[dict], limits: list[dict],
             retry_hint: str | None) -> dict:
    client = OpenAI(api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url or None,
                    timeout=settings.openai_timeout)
    prompt = (
        "당신은 건강 데이터 분석 도우미입니다. 아래 데이터를 바탕으로 지정된 "
        "스키마의 JSON으로만 답하세요. evidence_ids는 반드시 아래 '참고 근거' "
        "목록에 있는 id만 사용하세요. 모든 텍스트 값(summary, why, text 등)은 "
        "반드시 자연스러운 한국어로만 작성하고 영어·중국어·일본어 등 다른 언어를 "
        "절대 섞지 마세요.\n"
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
            logger.warning("analysis attempt failed", exc_info=True)

    if result is None:
        raise AnalysisError(f"분석 결과 검증에 실패했습니다: {last_error}")

    analysis = Analysis(trigger=trigger, result=result.model_dump_json())
    db.add(analysis)
    db.commit()
    return analysis


def run_scheduled_analysis(db: Session) -> Analysis | None:
    """Weekly cron entry point — never raises, so a bad LLM response or
    provider outage can't crash the background scheduler thread."""
    try:
        return run_analysis(db, trigger="weekly")
    except AnalysisError:
        logger.warning("weekly scheduled analysis failed", exc_info=True)
        return None
