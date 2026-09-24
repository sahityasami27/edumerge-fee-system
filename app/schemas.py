from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List
from app.models import EntryType, PaymentStatus, MismatchType

class ChargeCreate(BaseModel):
    fee_head_id: int
    amount_paise: int = Field(gt=0, description="Amount must be positive integer paise")
    installments: int = Field(default=1, ge=1)
    due_date: datetime

class ConcessionCreate(BaseModel):
    charge_id: int
    amount_paise: int = Field(gt=0)
    reason: str

class PaymentCreate(BaseModel):
    student_id: int
    amount_paise: int = Field(gt=0)
    method: str

class LedgerEntryResponse(BaseModel):
    id: int
    entry_type: EntryType
    amount_paise: int
    created_at: datetime
    note: Optional[str]
    model_config = ConfigDict(from_attributes=True)

class OutstandingResponse(BaseModel):
    student_id: int
    total_outstanding_paise: int