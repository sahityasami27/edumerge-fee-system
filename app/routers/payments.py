from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas import PaymentCreate
from app.services.payments import process_payment_intent, reverse_payment
from app.models import Payment
from app.deps import get_current_user_role, require_admin_or_accountant

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("")
def create_payment(
    payload: PaymentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_role)
):
    # Returns 409 if key exists with different payload, or original if same
    payment = process_payment_intent(db, payload, idempotency_key, actor=user["user"])
    return payment

@router.get("/{payment_id}")
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_role)
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment

@router.post("/{payment_id}/reverse")
def reverse_payment_endpoint(
    payment_id: int,
    reason: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin_or_accountant) # Reversal restricted by role[cite: 1]
):
    reverse_payment(db, payment_id, reason, actor=user["user"], role=user["role"])
    return {"status": "success", "message": "Payment reversed successfully"}