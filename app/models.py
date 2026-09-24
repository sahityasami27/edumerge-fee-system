from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from app.db import Base

class EntryType(str, enum.Enum):
    CHARGE = "CHARGE"
    CONCESSION = "CONCESSION"
    PAYMENT_ALLOCATION = "PAYMENT_ALLOCATION"
    REVERSAL = "REVERSAL"
    ADVANCE_CREDIT = "ADVANCE_CREDIT"

class PaymentStatus(str, enum.Enum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REVERSED = "REVERSED"

class MismatchType(str, enum.Enum):
    MISSING_INTERNALLY = "MISSING_INTERNALLY"
    MISSING_IN_SETTLEMENT = "MISSING_IN_SETTLEMENT"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DUPLICATE_IN_SETTLEMENT = "DUPLICATE_IN_SETTLEMENT"
    STATUS_MISMATCH = "STATUS_MISMATCH"

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    roll_no = Column(String, unique=True, index=True)
    name = Column(String)
    program = Column(String)

class FeeHead(Base):
    __tablename__ = "fee_heads"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)

class Charge(Base):
    __tablename__ = "charges"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    fee_head_id = Column(Integer, ForeignKey("fee_heads.id"), nullable=False)
    installment_no = Column(Integer, nullable=False)
    amount_paise = Column(Integer, nullable=False)
    due_date = Column(DateTime, nullable=False)

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    amount_paise = Column(Integer, nullable=False)
    method = Column(String, nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.INITIATED, nullable=False)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    gateway_ref = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class PaymentEvent(Base):
    __tablename__ = "payment_events"
    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    from_status = Column(String, nullable=True)
    to_status = Column(Enum(PaymentStatus), nullable=False)
    source = Column(String, nullable=False) 
    at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    charge_id = Column(Integer, ForeignKey("charges.id"), nullable=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    entry_type = Column(Enum(EntryType), nullable=False)
    amount_paise = Column(Integer, nullable=False)
    reverses_entry_id = Column(Integer, ForeignKey("ledger_entries.id"), nullable=True)
    note = Column(String)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True, nullable=False)
    payload = Column(JSON, nullable=False)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class SettlementRecord(Base):
    __tablename__ = "settlement_records"
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String, index=True, nullable=False)
    gateway_ref = Column(String, nullable=False)
    amount_paise = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    settled_on = Column(DateTime, nullable=False)

class ReconResult(Base):
    __tablename__ = "recon_results"
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String, index=True, nullable=False)
    gateway_ref = Column(String, nullable=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    mismatch_type = Column(Enum(MismatchType), nullable=False)
    resolved = Column(Boolean, default=False, nullable=False)
    resolution_note = Column(String, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String, nullable=False)
    role = Column(String, nullable=False)
    action = Column(String, nullable=False)
    entity = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)
    before_json = Column(JSON, nullable=True)
    after_json = Column(JSON, nullable=True)
    at = Column(DateTime, default=lambda: datetime.now(timezone.utc))