import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class Policy(Base):
    __tablename__ = "policies"

    id = Column(String, primary_key=True, default=lambda: gen_id("pol"))
    name = Column(String, nullable=False)
    framework = Column(String, default="Internal")
    status = Column(String, default="Draft")  # Active | Draft
    source_filename = Column(String, nullable=True)
    raw_text = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    controls = relationship("Control", back_populates="policy", cascade="all, delete-orphan")
    scans = relationship("Scan", back_populates="policy", cascade="all, delete-orphan")


class Control(Base):
    __tablename__ = "controls"

    id = Column(String, primary_key=True, default=lambda: gen_id("CTRL"))
    policy_id = Column(String, ForeignKey("policies.id"), nullable=False)
    target = Column(String, nullable=False)
    metric = Column(String, nullable=False)
    operator = Column(String, default="<")  # < | > | >= | <= | = | !=
    threshold = Column(String, nullable=False)
    severity = Column(String, default="Medium")  # High | Medium | Low

    policy = relationship("Policy", back_populates="controls")


class Scan(Base):
    __tablename__ = "scans"

    id = Column(String, primary_key=True, default=lambda: gen_id("scan"))
    policy_id = Column(String, ForeignKey("policies.id"), nullable=False)
    evidence_json = Column(JSON, nullable=False)
    score = Column(Integer, default=0)
    status = Column(String, default="Compliant")  # Compliant | At Risk
    assets = Column(Integer, default=0)
    run_at = Column(DateTime, default=datetime.utcnow)

    policy = relationship("Policy", back_populates="scans")
    results = relationship("ScanResult", back_populates="scan", cascade="all, delete-orphan")


class ScanResult(Base):
    __tablename__ = "scan_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False)
    control_id = Column(String, ForeignKey("controls.id"), nullable=True)
    name = Column(String, nullable=False)
    target = Column(String, nullable=False)
    expected = Column(String, nullable=False)
    actual = Column(String, nullable=False)
    status = Column(String, nullable=False)  # Passed | Failed | Not Evaluated
    reason = Column(Text, nullable=True)

    scan = relationship("Scan", back_populates="results")
