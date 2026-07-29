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
