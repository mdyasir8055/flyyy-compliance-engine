from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services.pdf_extract import extract_text_from_pdf
from app.services.groq_client import extract_controls_from_policy

router = APIRouter(prefix="/api/policies", tags=["policies"])


def _to_policy_out(p: models.Policy) -> schemas.PolicyOut:
    return schemas.PolicyOut(
        id=p.id, name=p.name, framework=p.framework, status=p.status,
        uploaded_at=p.uploaded_at, controls_count=len(p.controls),
    )


@router.get("", response_model=list[schemas.PolicyOut])
def list_policies(db: Session = Depends(get_db)):
    policies = db.query(models.Policy).order_by(models.Policy.uploaded_at.desc()).all()
    return [_to_policy_out(p) for p in policies]


@router.get("/{policy_id}", response_model=schemas.PolicyDetailOut)
def get_policy(policy_id: str, db: Session = Depends(get_db)):
    p = db.query(models.Policy).filter(models.Policy.id == policy_id).first()
    if not p:
        raise HTTPException(404, "Policy not found")
    return schemas.PolicyDetailOut(
        id=p.id, name=p.name, framework=p.framework, status=p.status,
        uploaded_at=p.uploaded_at, controls_count=len(p.controls),
        controls=[schemas.ControlOut.model_validate(c) for c in p.controls],
    )


@router.post("/upload", response_model=schemas.PolicyDetailOut)
async def upload_policy(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    framework: str = Form("Internal"),
    db: Session = Depends(get_db),
):
    if file.content_type != "application/pdf" and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    raw_bytes = await file.read()
    text = extract_text_from_pdf(raw_bytes)
    if not text:
        raise HTTPException(422, "Could not extract any text from this PDF")

    try:
        extracted = extract_controls_from_policy(text)
    except Exception as e:
        raise HTTPException(502, f"Control extraction failed: {e}")

    policy = models.Policy(
        name=name or file.filename.rsplit(".", 1)[0],
        framework=framework,
        status="Active",
        source_filename=file.filename,
        raw_text=text[:50000],
    )
    db.add(policy)
    db.flush()  # get policy.id

    for c in extracted:
        db.add(models.Control(
            policy_id=policy.id,
            target=str(c.get("target", "unknown_target")),
            metric=str(c.get("metric", "unknown_metric")),
            operator=str(c.get("operator", "<")),
            threshold=str(c.get("threshold", "")),
            severity=str(c.get("severity", "Medium")).capitalize(),
        ))

    db.commit()
    db.refresh(policy)

    return schemas.PolicyDetailOut(
        id=policy.id, name=policy.name, framework=policy.framework, status=policy.status,
        uploaded_at=policy.uploaded_at, controls_count=len(policy.controls),
        controls=[schemas.ControlOut.model_validate(c) for c in policy.controls],
    )


@router.delete("/{policy_id}")
def delete_policy(policy_id: str, db: Session = Depends(get_db)):
    p = db.query(models.Policy).filter(models.Policy.id == policy_id).first()
    if not p:
        raise HTTPException(404, "Policy not found")
    db.delete(p)
    db.commit()
    return {"ok": True}
