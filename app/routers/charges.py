from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas import ChargeCreate, ConcessionCreate
from app.services.ledger import create_charges, apply_concession
from app.deps import require_admin

router = APIRouter(prefix="/students/{student_id}", tags=["charges"])

@router.post("/charges")
def create_student_charges(
    student_id: int,
    payload: ChargeCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin)
):
    charges = create_charges(
        db=db,
        student_id=student_id,
        fee_head_id=payload.fee_head_id,
        total_amount_paise=payload.amount_paise,
        installments=payload.installments,
        due_date=payload.due_date,
        actor=user["user"]
    )
    return {"status": "success", "created": len(charges)}

@router.post("/concessions")
def create_student_concession(
    student_id: int,
    payload: ConcessionCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin) # Only admin can issue concessions[cite: 1]
):
    entry = apply_concession(
        db=db,
        student_id=student_id,
        charge_id=payload.charge_id,
        amount_paise=payload.amount_paise,
        reason=payload.reason,
        actor=user["user"]
    )
    return entry