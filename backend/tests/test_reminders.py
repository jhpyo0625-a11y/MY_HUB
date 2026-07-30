from datetime import date, datetime


def _make_supp(db_session_factory):
    from app.models import Supplement, SupplementSchedule
    db = db_session_factory()
    s = Supplement(product_name="비타민D")
    s.schedules.append(SupplementSchedule(
        days_of_week="0123456", time_of_day="09:00", servings=1))
    db.add(s)
    db.commit()
    return db, s.schedules[0].id


def test_sends_reminder_when_due(db_session_factory, monkeypatch):
    from app import reminders
    db, schedule_id = _make_supp(db_session_factory)

    sent = []
    monkeypatch.setattr(reminders, "send_push",
                        lambda db, payload: sent.append(payload) or True)

    now = datetime(2026, 7, 29, 9, 0)  # Wed, matches time_of_day
    processed = reminders.check_and_send_reminders(db, now)
    assert processed == [schedule_id]
    assert sent[0]["body"] == "비타민D 드실 시간이에요"

    from app.models import ReminderLog
    assert db.query(ReminderLog).filter_by(
        schedule_id=schedule_id, date=date(2026, 7, 29)).count() == 1


def test_no_duplicate_reminder_same_day(db_session_factory, monkeypatch):
    from app import reminders
    db, _ = _make_supp(db_session_factory)
    monkeypatch.setattr(reminders, "send_push", lambda db, payload: True)

    now = datetime(2026, 7, 29, 9, 0)
    reminders.check_and_send_reminders(db, now)
    assert reminders.check_and_send_reminders(db, now) == []


def test_no_reminder_when_time_does_not_match(db_session_factory, monkeypatch):
    from app import reminders
    db, _ = _make_supp(db_session_factory)
    monkeypatch.setattr(reminders, "send_push", lambda db, payload: True)

    now = datetime(2026, 7, 29, 10, 0)
    assert reminders.check_and_send_reminders(db, now) == []


def test_inactive_supplement_skipped(db_session_factory, monkeypatch):
    from app import reminders
    from app.models import Supplement
    db, _ = _make_supp(db_session_factory)
    db.query(Supplement).one().active = False
    db.commit()
    monkeypatch.setattr(reminders, "send_push", lambda db, payload: True)

    now = datetime(2026, 7, 29, 9, 0)
    assert reminders.check_and_send_reminders(db, now) == []


def test_records_log_even_when_push_fails(db_session_factory, monkeypatch):
    from app import reminders
    db, schedule_id = _make_supp(db_session_factory)
    monkeypatch.setattr(reminders, "send_push", lambda db, payload: False)

    now = datetime(2026, 7, 29, 9, 0)
    assert reminders.check_and_send_reminders(db, now) == [schedule_id]
