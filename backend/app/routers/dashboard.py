from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=schemas.DashboardSummary)
def summary(db: Session = Depends(get_db)):
    policies_count = db.query(func.count(models.Policy.id)).scalar() or 0
    scans_count = db.query(func.count(models.Scan.id)).scalar() or 0
    passed = db.query(func.count(models.ScanResult.id)).filter(
        models.ScanResult.status == "Passed"
    ).scalar() or 0
    failed = db.query(func.count(models.ScanResult.id)).filter(
        models.ScanResult.status == "Failed"
    ).scalar() or 0
    avg_score = db.query(func.avg(models.Scan.score)).scalar()

    return schemas.DashboardSummary(
        policies=policies_count,
        scans=scans_count,
        passed=passed,
        failed=failed,
        score=round(avg_score) if avg_score else 0,
    )
