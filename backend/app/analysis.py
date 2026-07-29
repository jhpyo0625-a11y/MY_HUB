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
