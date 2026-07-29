import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..analysis import AnalysisError, run_analysis
from ..auth import require_auth
from ..db import get_db
from ..models import Analysis

router = APIRouter(prefix="/api/analysis", tags=["analysis"],
                   dependencies=[Depends(require_auth)])


def analysis_to_dict(a: Analysis) -> dict:
    return {"id": a.id, "run_at": a.run_at.isoformat(), "trigger": a.trigger,
           **json.loads(a.result)}


@router.post("/run", status_code=201)
def trigger_analysis(db: Session = Depends(get_db)):
    try:
        analysis = run_analysis(db, trigger="manual")
    except AnalysisError as exc:
        raise HTTPException(502, str(exc))
    return analysis_to_dict(analysis)


@router.get("/latest")
def latest_analysis(db: Session = Depends(get_db)):
    a = db.query(Analysis).order_by(Analysis.run_at.desc()).first()
    return analysis_to_dict(a) if a else None


@router.get("")
def list_analyses(db: Session = Depends(get_db)):
    rows = db.query(Analysis).order_by(Analysis.run_at.desc()).all()
    return [{"id": a.id, "run_at": a.run_at.isoformat(), "trigger": a.trigger,
            "summary": json.loads(a.result)["summary"]} for a in rows]


@router.get("/{analysis_id}")
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    a = db.get(Analysis, analysis_id)
    if a is None:
        raise HTTPException(404, "리포트를 찾을 수 없습니다")
    return analysis_to_dict(a)
