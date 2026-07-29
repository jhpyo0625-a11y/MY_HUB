from datetime import date, datetime

import pytest
from sqlalchemy.exc import IntegrityError


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


def test_cascade_delete_removes_children(db_session_factory):
    from app.models import (
        Meal,
        MealItem,
        Supplement,
        SupplementIngredient,
        SupplementSchedule,
    )

    db = db_session_factory()

    # Test Meal cascade delete
    meal = Meal(eaten_at=datetime(2026, 7, 29, 12, 0), dish_name="테스트식사")
    meal.items.append(MealItem(name="음식1", amount="100g"))
    meal.items.append(MealItem(name="음식2", amount="50g"))
    db.add(meal)
    db.commit()

    assert db.query(MealItem).count() == 2
    db.delete(meal)
    db.commit()
    assert db.query(MealItem).count() == 0

    # Test Supplement cascade delete
    supp = Supplement(brand="테스트", product_name="보충제")
    supp.ingredients.append(SupplementIngredient(
        ingredient_code="test_ing", amount=500, unit="mg"))
    supp.schedules.append(SupplementSchedule(
        days_of_week="0123456", time_of_day="09:00", servings=1))
    db.add(supp)
    db.commit()

    assert db.query(SupplementIngredient).count() == 1
    assert db.query(SupplementSchedule).count() == 1
    db.delete(supp)
    db.commit()
    assert db.query(SupplementIngredient).count() == 0
    assert db.query(SupplementSchedule).count() == 0


def test_intake_unique_constraint(db_session_factory):
    from app.models import IntakeLog, Supplement, SupplementSchedule

    db = db_session_factory()

    # Create a Supplement and SupplementSchedule to get a valid schedule_id
    supp = Supplement(brand="테스트", product_name="보충제")
    supp.schedules.append(SupplementSchedule(
        days_of_week="0123456", time_of_day="09:00", servings=1))
    db.add(supp)
    db.commit()

    schedule_id = supp.schedules[0].id
    test_date = date(2026, 7, 29)

    # Insert first IntakeLog
    db.add(IntakeLog(schedule_id=schedule_id, date=test_date, status="taken"))
    db.commit()

    # Try to insert a second IntakeLog with same (schedule_id, date) — should fail
    db.add(IntakeLog(schedule_id=schedule_id, date=test_date, status="taken"))
    with pytest.raises(IntegrityError):
        db.commit()
