from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import require_auth
from ..db import get_db
from ..models import MetricDefinition, MetricEntry

router = APIRouter(prefix="/api/metrics", tags=["metrics"],
                   dependencies=[Depends(require_auth)])


@router.get("/definitions")
def list_definitions(db: Session = Depends(get_db)):
    defs = db.query(MetricDefinition).all()
    return [{"code": d.code, "name_ko": d.name_ko, "unit": d.unit,
             "domain": d.domain, "input_type": d.input_type,
             "range_low": d.range_low, "range_high": d.range_high}
            for d in defs]


def latest_metrics_dict(db: Session) -> dict:
    entries = (db.query(MetricEntry)
               .order_by(MetricEntry.measured_at.asc()).all())
    out: dict[str, dict] = {}
    for e in entries:  # ascending — last write per code wins
        out[e.metric_code] = {"value_num": e.value_num,
                              "value_text": e.value_text,
                              "measured_at": e.measured_at.isoformat()}
    return out


@router.get("/latest")
def latest_per_metric(db: Session = Depends(get_db)):
    return latest_metrics_dict(db)


@router.get("/entries")
def list_entries(code: str, limit: int = 100, db: Session = Depends(get_db)):
    q = (db.query(MetricEntry).filter(MetricEntry.metric_code == code)
         .order_by(MetricEntry.measured_at.desc()).limit(limit))
    return [{"id": e.id, "metric_code": e.metric_code,
             "value_num": e.value_num, "value_text": e.value_text,
             "measured_at": e.measured_at.isoformat()} for e in q]


class EntryIn(BaseModel):
    metric_code: str
    value_num: float | None = None
    value_text: str | None = None
    measured_at: datetime | None = None


@router.post("/entries", status_code=201)
def create_entry(body: EntryIn, db: Session = Depends(get_db)):
    d = db.get(MetricDefinition, body.metric_code)
    if d is None:
        raise HTTPException(404, "알 수 없는 항목입니다")
    if d.input_type in ("number", "scale") and body.value_num is None:
        raise HTTPException(422, "숫자 값이 필요합니다")
    if d.input_type == "text" and not body.value_text:
        raise HTTPException(422, "텍스트 값이 필요합니다")
    if d.input_type == "scale" and body.value_num not in (0, 1, 2, 3):
        raise HTTPException(422, "0~3 값이어야 합니다")
    e = MetricEntry(metric_code=body.metric_code, value_num=body.value_num,
                    value_text=body.value_text,
                    measured_at=body.measured_at or datetime.now())
    db.add(e)
    db.commit()
    return {"id": e.id}
