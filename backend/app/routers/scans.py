from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services.evaluator import evaluate_control, compare_value
from app.services.groq_client import generate_audit_reasoning, reconcile_evidence

router = APIRouter(prefix="/api/scans", tags=["scans"])


def _to_scan_out(s: models.Scan) -> schemas.ScanOut:
    return schemas.ScanOut(
        id=s.id, policy_id=s.policy_id, policy_name=s.policy.name if s.policy else None,
        score=s.score, status=s.status, assets=s.assets, run_at=s.run_at,
    )


@router.get("", response_model=list[schemas.ScanOut])
def list_scans(db: Session = Depends(get_db)):
    scans = db.query(models.Scan).order_by(models.Scan.run_at.desc()).all()
    return [_to_scan_out(s) for s in scans]


def _run_legacy_evaluation(control, evidence: dict) -> list[dict]:
    """
    Fallback path used when AI reconciliation is unavailable (no Groq key, Groq
    error, etc). Requires control.target to exactly match an asset name in the
    evidence - the original behavior. Always returns a list so callers can treat
    both paths the same way (0 or 1 "matches" instead of many).
    """
    outcome = evaluate_control(control, evidence)
    if outcome["passed"] is None:
        return []
    return [{
        "asset_name": control.target,
        "value": outcome["actual"],
        "passed": outcome["passed"],
        "note": None,
    }]


@router.post("", response_model=schemas.ScanDetailOut)
def run_scan(payload: schemas.ScanCreate, db: Session = Depends(get_db)):
    policy = db.query(models.Policy).filter(models.Policy.id == payload.policy_id).first()
    if not policy:
        raise HTTPException(404, "Policy not found")
    if not policy.controls:
        raise HTTPException(422, "This policy has no controls to evaluate")

    evidence = payload.evidence
    assets = evidence.get("assets", [])

    scan = models.Scan(
        policy_id=policy.id,
        evidence_json=evidence,
        assets=len(assets),
    )
    db.add(scan)
    db.flush()

    # --- AI reconciliation step: figure out which evidence asset(s) and field(s) ---
    # each control actually applies to, regardless of naming differences. Falls
    # back cleanly to the old exact-name-match behavior if this step fails for
    # any reason (no API key, Groq error, malformed response, etc), so a scan
    # never hard-fails just because reconciliation had an issue.
    reconciliation_by_control: dict[str, list[dict]] = {}
    reconciliation_available = True
    try:
        controls_payload = [
            {"id": c.id, "target": c.target, "metric": c.metric,
             "operator": c.operator, "threshold": c.threshold}
            for c in policy.controls
        ]
        raw = reconcile_evidence(controls_payload, evidence)
        for entry in raw:
            reconciliation_by_control[entry.get("control_id")] = entry.get("matches", [])
    except Exception:
        reconciliation_available = False

    passed_count, failed_count, evaluated_count = 0, 0, 0

    for control in policy.controls:
        # Build the list of (asset_name, actual_value, note) this control applies to.
        matched: list[dict] = []

        if reconciliation_available and control.id in reconciliation_by_control:
            for m in reconciliation_by_control[control.id]:
                if m.get("confidence") == "low":
                    # Never silently trust a low-confidence AI match - surface it
                    # as Not Evaluated with an explanation instead of guessing.
                    db.add(models.ScanResult(
                        scan_id=scan.id,
                        control_id=control.id,
                        name=f"{control.metric.replace('_', ' ').title()}",
                        target=m.get("asset_name", control.target),
                        expected=f"{control.operator} {control.threshold}",
                        actual="N/A",
                        status="Not Evaluated",
                        reason=(
                            f"A possible match was found ({m.get('note', 'no detail provided')}) "
                            "but confidence was too low to evaluate automatically. Needs manual review."
                        ),
                    ))
                    continue
                raw_value = m.get("value")
                bool_interp = m.get("boolean_interpretation")

                # For yes/no controls, prefer the AI's interpreted true/false over the
                # raw value when the raw value isn't already a literal true/false -
                # e.g. scalingPolicy: "elastic" means the requirement IS met, but
                # "elastic" != True as a plain string comparison.
                is_boolean_control = (
                    control.operator in ("=", "!=")
                    and str(control.threshold).strip().lower() in ("true", "false")
                )
                value_for_grading = raw_value
                if is_boolean_control and bool_interp is not None:
                    is_literal_bool = isinstance(raw_value, bool) or (
                        isinstance(raw_value, str) and raw_value.strip().lower() in ("true", "false")
                    )
                    if not is_literal_bool:
                        value_for_grading = bool_interp

                matched.append({
                    "asset_name": m.get("asset_name", control.target),
                    "value": raw_value,
                    "value_for_grading": value_for_grading,
                    "passed": compare_value(value_for_grading, control.operator, control.threshold),
                    "note": m.get("note"),
                })
        elif not reconciliation_available:
            matched = _run_legacy_evaluation(control, evidence)

        if not matched:
            db.add(models.ScanResult(
                scan_id=scan.id,
                control_id=control.id,
                name=f"{control.metric.replace('_', ' ').title()}",
                target=control.target,
                expected=f"{control.operator} {control.threshold}",
                actual="N/A",
                status="Not Evaluated",
                reason=f"No matching evidence was found for '{control.metric}' on '{control.target}'.",
            ))
            continue

        for m in matched:
            evaluated_count += 1
            if m["passed"]:
                passed_count += 1
            else:
                failed_count += 1

            reason = generate_audit_reasoning(
                {"target": m["asset_name"], "metric": control.metric,
                 "operator": control.operator, "threshold": control.threshold},
                m["value"], m["passed"],
            )
            extra_notes = []
            if m.get("note"):
                extra_notes.append(f"Matched via AI reconciliation: {m['note']}")
            if m.get("value_for_grading") is not None and m["value_for_grading"] != m["value"]:
                extra_notes.append(
                    f"Raw value '{m['value']}' was interpreted as "
                    f"{'meeting' if m['value_for_grading'] else 'not meeting'} the requirement."
                )
            if extra_notes:
                reason = f"{reason} ({'; '.join(extra_notes)})"

            db.add(models.ScanResult(
                scan_id=scan.id,
                control_id=control.id,
                name=f"{control.metric.replace('_', ' ').title()}",
                target=m["asset_name"],
                expected=f"{control.operator} {control.threshold}",
                actual=str(m["value"]),
                status="Passed" if m["passed"] else "Failed",
                reason=reason,
            ))

    score = round((passed_count / evaluated_count) * 100) if evaluated_count else 0
    scan.score = score
    scan.status = "Compliant" if score >= 80 else "At Risk"

    db.commit()
    db.refresh(scan)

    return schemas.ScanDetailOut(
        id=scan.id, policy_id=scan.policy_id, policy_name=policy.name,
        score=scan.score, status=scan.status, assets=scan.assets, run_at=scan.run_at,
        results=[schemas.ScanResultOut.model_validate(r) for r in scan.results],
    )


@router.get("/{scan_id}", response_model=schemas.ScanDetailOut)
def get_scan(scan_id: str, db: Session = Depends(get_db)):
    scan = db.query(models.Scan).filter(models.Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(404, "Scan not found")
    return schemas.ScanDetailOut(
        id=scan.id, policy_id=scan.policy_id, policy_name=scan.policy.name if scan.policy else None,
        score=scan.score, status=scan.status, assets=scan.assets, run_at=scan.run_at,
        results=[schemas.ScanResultOut.model_validate(r) for r in scan.results],
    )