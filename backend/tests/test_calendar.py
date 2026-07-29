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
