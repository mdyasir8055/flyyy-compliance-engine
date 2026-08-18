from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=schemas.DashboardSummary)
def summary(
    db: Session = Depends(get_db),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    scan_query = db.query(models.Scan)
    if start_date:
        scan_query = scan_query.filter(models.Scan.run_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        scan_query = scan_query.filter(models.Scan.run_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()))

    scan_ids = [s.id for s in scan_query.all()]

    policies_count = db.query(func.count(models.Policy.id)).scalar() or 0
    scans_count = len(scan_ids)

    if scan_ids:
        result_query = db.query(models.ScanResult).filter(models.ScanResult.scan_id.in_(scan_ids))
        passed = result_query.filter(models.ScanResult.status == "Passed").count()
        failed = result_query.filter(models.ScanResult.status == "Failed").count()
        avg_score = db.query(func.avg(models.Scan.score)).filter(models.Scan.id.in_(scan_ids)).scalar()
    else:
        passed = failed = 0
        avg_score = None

    return schemas.DashboardSummary(
        policies=policies_count,
        scans=scans_count,
        passed=passed,
        failed=failed,
        score=round(avg_score) if avg_score else 0,
    )


@router.delete("/reset")
def reset_all_data(db: Session = Depends(get_db)):
    db.query(models.ScanResult).delete()
    db.query(models.Scan).delete()
    db.query(models.Control).delete()
    db.query(models.Policy).delete()
    db.commit()
    return {"reset": True}
