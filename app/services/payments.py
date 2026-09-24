from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Payment, PaymentStatus, PaymentEvent, AuditLog
from app.schemas import PaymentCreate
from app.services.allocation import allocate_payment
from datetime import datetime, timezone

# Centralized state machine
ALLOWED_TRANSITIONS = {
    PaymentStatus.INITIATED: [PaymentStatus.PENDING, PaymentStatus.FAILED],
    PaymentStatus.PENDING: [PaymentStatus.SUCCESS, PaymentStatus.FAILED],
    PaymentStatus.SUCCESS: [PaymentStatus.REVERSED],
    PaymentStatus.FAILED: [],
    PaymentStatus.REVERSED: []
}

def transition_payment_status(
    db: Session, 
    payment: Payment, 
    new_status: PaymentStatus, 
    source: str, 
    actor: str
):
    if new_status not in ALLOWED_TRANSITIONS[payment.status]:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid transition from {payment.status} to {new_status}"
        )
    
    event = PaymentEvent(
        payment_id=payment.id,
        from_status=payment.status,
        to_status=new_status,
        source=source
    )
    db.add(event)
    
    payment.status = new_status
    db.commit()
    db.refresh(payment)

    # Money moves in the ledger ONLY on SUCCESS[cite: 1]
    if new_status == PaymentStatus.SUCCESS:
        allocate_payment(db, payment, actor)

def process_payment_intent(
    db: Session, 
    payload: PaymentCreate, 
    idempotency_key: str, 
    actor: str
) -> Payment:
    # Idempotency check[cite: 1]
    existing_payment = db.query(Payment).filter(Payment.idempotency_key == idempotency_key).first()
    
    if existing_payment:
        # Same key, different body -> 409 Conflict[cite: 1]
        if (existing_payment.student_id != payload.student_id or 
            existing_payment.amount_paise != payload.amount_paise or 
            existing_payment.method != payload.method):
            raise HTTPException(status_code=409, detail="Idempotency key already used with different payload")
        # Same key, same body -> return original[cite: 1]
        return existing_payment

    new_payment = Payment(
        student_id=payload.student_id,
        amount_paise=payload.amount_paise,
        method=payload.method,
        idempotency_key=idempotency_key,
        status=PaymentStatus.INITIATED
    )
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)
    
    # Immediately transition to PENDING (simulating gateway handoff)
    transition_payment_status(db, new_payment, PaymentStatus.PENDING, source="api", actor=actor)
    return new_payment

def reverse_payment(db: Session, payment_id: int, reason: str, actor: str, role: str):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
        
    # Validates reversal is only from SUCCESS and enforces once-per-payment rule[cite: 1]
    transition_payment_status(db, payment, PaymentStatus.REVERSED, source="admin", actor=actor)

    audit = AuditLog(
        actor=actor, role=role, action="REVERSE_PAYMENT", 
        entity="Payment", entity_id=payment.id, 
        after_json={"reason": reason}
    )
    db.add(audit)
    db.commit()
    
    from app.services.allocation import reverse_allocations
    reverse_allocations(db, payment, actor)