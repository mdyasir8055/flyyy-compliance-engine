"""
One-off script to insert sample policies/controls/scans/results with varied
run_at dates, for testing the dashboard's date-range filter.

This is NOT part of the app - it's a dev/testing utility only. Run it once,
inspect the dashboard filter, then use "Reset all data" to clear it out
before your real submission/demo.

Run inside the backend container (reuses its installed dependencies):
    docker compose exec backend python -m app.seed_test_data

Or locally if you have the backend's requirements installed and Postgres
port 5432 exposed to your host (it is, per docker-compose.yml):
    DATABASE_URL=postgresql://flyyy:flyyy@localhost:5432/flyyy python backend/app/seed_test_data.py
"""
import random
from datetime import datetime, timedelta

from app.database import SessionLocal, engine, Base
from app import models

Base.metadata.create_all(bind=engine)

db = SessionLocal()

policy = models.Policy(
    name="Sample Seeded Policy (for filter testing)",
    framework="Internal",
    status="Active",
    source_filename="seed_test_data.py",
    raw_text="Sample policy inserted for testing the dashboard date filter.",
)
db.add(policy)
db.flush()

control_specs = [
    ("production_server", "cpu_utilization", "<", "85%", "High"),
    ("production_server", "memory_utilization", "<", "80%", "Medium"),
    ("production_database", "encryption_at_rest", "=", "true", "High"),
]
controls = []
for target, metric, op, threshold, sev in control_specs:
    c = models.Control(policy_id=policy.id, target=target, metric=metric,
                        operator=op, threshold=threshold, severity=sev)
    db.add(c)
    controls.append(c)
db.flush()

# Days-ago offsets chosen to land in different buckets: today, within 7d,
# within 30d, and outside 30d entirely - so every filter preset has
# something to show and something to exclude.
days_ago_offsets = [0, 1, 3, 6, 10, 15, 22, 29, 45, 60]

for days_ago in days_ago_offsets:
    run_at = datetime.utcnow() - timedelta(days=days_ago)
    passed = random.randint(1, 3)
    failed = random.randint(0, 2)
    total = passed + failed
    score = round((passed / total) * 100) if total else 0

    scan = models.Scan(
        policy_id=policy.id,
        evidence_json={"assets": [{"name": "seed-asset-01", "note": "synthetic test data"}]},
        score=score,
        status="Compliant" if score >= 80 else "At Risk",
        assets=1,
        run_at=run_at,
    )
    db.add(scan)
    db.flush()

    for i in range(passed):
        db.add(models.ScanResult(
            scan_id=scan.id, control_id=controls[i % len(controls)].id,
            name=f"Sample Control {i+1}", target="seed-asset-01",
            expected="< 85%", actual="70", status="Passed",
            reason="Synthetic seeded result for date-filter testing.",
        ))
    for i in range(failed):
        db.add(models.ScanResult(
            scan_id=scan.id, control_id=controls[i % len(controls)].id,
            name=f"Sample Control {i+1}", target="seed-asset-01",
            expected="< 85%", actual="95", status="Failed",
            reason="Synthetic seeded result for date-filter testing.",
        ))

db.commit()
db.close()

print(f"Seeded 1 policy, {len(controls)} controls, {len(days_ago_offsets)} scans "
      f"dated {min(days_ago_offsets)}-{max(days_ago_offsets)} days ago.")
print("Test the dashboard filter now. Use 'Reset all data' when done to clear this out.")