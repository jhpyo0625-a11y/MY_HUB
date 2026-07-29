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
