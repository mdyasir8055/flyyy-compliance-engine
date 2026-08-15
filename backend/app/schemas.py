from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ---------- Controls ----------

class ControlBase(BaseModel):
    target: str
    metric: str
    operator: str = "<"
    threshold: str
    severity: str = "Medium"


class ControlCreate(ControlBase):
    id: Optional[str] = None


class ControlUpdate(BaseModel):
    target: Optional[str] = None
    metric: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[str] = None
    severity: Optional[str] = None


class ControlOut(ControlBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    policy_id: str


# ---------- Policies ----------

class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    framework: str
    status: str
    uploaded_at: datetime
    controls_count: int = 0


class PolicyDetailOut(PolicyOut):
    controls: list[ControlOut] = []


# ---------- Scans ----------

class ScanCreate(BaseModel):
    policy_id: str
    evidence: dict[str, Any]


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    policy_id: str
    policy_name: Optional[str] = None
    score: int
    status: str
    assets: int
    run_at: datetime


class ScanResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    target: str
    expected: str
    actual: str
    status: str
    reason: Optional[str] = None


class ScanDetailOut(ScanOut):
    results: list[ScanResultOut] = []


# ---------- Dashboard ----------

class DashboardSummary(BaseModel):
    policies: int
    scans: int
    passed: int
    failed: int
    score: int
