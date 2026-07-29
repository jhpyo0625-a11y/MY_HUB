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
