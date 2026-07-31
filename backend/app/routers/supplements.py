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
