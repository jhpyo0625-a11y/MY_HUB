import logging
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from .models import ReminderLog, Supplement
from .push import send_push

logger = logging.getLogger(__name__)


def check_and_send_reminders(db: Session, now: datetime) -> list[int]:
    """Send one push per due, not-yet-sent supplement schedule slot this
    minute. Returns the schedule_ids processed (sent or attempted)."""
    dow = str(now.weekday())  # 0=Mon … 6=Sun, matches days_of_week convention
    hhmm = now.strftime("%H:%M")
    today = now.date()

    supps = (db.query(Supplement).filter(Supplement.active.is_(True))
             .options(joinedload(Supplement.schedules)).all())
    processed: list[int] = []
    for supp in supps:
        for sched in supp.schedules:
            if dow not in sched.days_of_week or sched.time_of_day != hhmm:
                continue
            already = (db.query(ReminderLog)
                      .filter_by(schedule_id=sched.id, date=today).first())
            if already:
                continue
            send_push(db, {
                "title": "복용 알림",
                "body": f"{supp.product_name} 드실 시간이에요",
            })
            # Recorded whether push succeeded or not — one attempt per slot
            # per day; a dead subscription is covered by the dashboard's
            # existing pending-intake checklist (spec §6), not by retrying
            # every minute.
            db.add(ReminderLog(schedule_id=sched.id, date=today, sent_at=now))
            db.commit()
            processed.append(sched.id)
    return processed
