from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import WebhookEvent, Payment, PaymentStatus
from app.services.payments import transition_payment_status

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

class GatewayPayload(BaseModel):
    event_id: str
    gateway_ref: str
    payment_id: int
    status: PaymentStatus

@router.post("/gateway")
def gateway_webhook(payload: GatewayPayload, db: Session = Depends(get_db)):
    # 1. Duplicate event check returns 200 and does nothing[cite: 1]
    existing_event = db.query(WebhookEvent).filter(WebhookEvent.event_id == payload.event_id).first()
    if existing_event:
        return {"status": "ignored", "message": "Duplicate event"}

    # Record the raw event for audit
    event_record = WebhookEvent(
        event_id=payload.event_id,
        payload=payload.model_dump()
    )
    db.add(event_record)
    
    payment = db.query(Payment).filter(Payment.id == payload.payment_id).first()
    if not payment:
        db.commit()
        return {"status": "logged", "message": "Payment ID not found"}

    payment.gateway_ref = payload.gateway_ref

    # 2. Out-of-order check: do not apply SUCCESS if already FAILED/REVERSED[cite: 1]
    if payment.status in [PaymentStatus.FAILED, PaymentStatus.REVERSED]:
        # Leave state alone, it will show up as a mismatch in reconciliation review[cite: 1]
        db.commit()
        return {"status": "anomaly_flagged", "message": "Out-of-order event skipped"}

    try:
        transition_payment_status(db, payment, payload.status, source="webhook", actor="gateway")
    except HTTPException:
        # Ignore invalid transitions quietly in webhook, log in DB
        pass

    db.commit()
    return {"status": "processed"}