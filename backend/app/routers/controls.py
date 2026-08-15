from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/policies/{policy_id}/controls", tags=["controls"])


@router.post("", response_model=schemas.ControlOut)
def add_control(policy_id: str, payload: schemas.ControlCreate, db: Session = Depends(get_db)):
    policy = db.query(models.Policy).filter(models.Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(404, "Policy not found")

    control = models.Control(
        policy_id=policy_id,
        target=payload.target,
        metric=payload.metric,
        operator=payload.operator,
        threshold=payload.threshold,
        severity=payload.severity,
    )
    if payload.id:
        control.id = payload.id
    db.add(control)
    db.commit()
    db.refresh(control)
    return control


@router.put("/{control_id}", response_model=schemas.ControlOut)
def update_control(policy_id: str, control_id: str, payload: schemas.ControlUpdate, db: Session = Depends(get_db)):
    control = db.query(models.Control).filter(
        models.Control.id == control_id, models.Control.policy_id == policy_id
    ).first()
    if not control:
        raise HTTPException(404, "Control not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(control, field, value)

    db.commit()
    db.refresh(control)
    return control


@router.delete("/{control_id}")
def delete_control(policy_id: str, control_id: str, db: Session = Depends(get_db)):
    control = db.query(models.Control).filter(
        models.Control.id == control_id, models.Control.policy_id == policy_id
    ).first()
    if not control:
        raise HTTPException(404, "Control not found")
    db.delete(control)
    db.commit()
    return {"ok": True}
