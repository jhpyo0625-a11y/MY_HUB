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
