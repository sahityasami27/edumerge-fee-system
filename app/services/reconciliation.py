import csv
import io
from sqlalchemy.orm import Session
from app.models import Payment, SettlementRecord, ReconResult, MismatchType, PaymentStatus
import uuid
from datetime import datetime

def process_settlement_csv(db: Session, file_contents: bytes) -> str:
    """
    Expects CSV with columns: gateway_ref, amount_paise, status, settled_on
    """
    batch_id = f"batch_{uuid.uuid4().hex[:8]}"
    reader = csv.DictReader(io.StringIO(file_contents.decode("utf-8")))
    
    seen_refs = set()
    
    for row in reader:
        ref = row.get("gateway_ref")
        amt = int(row.get("amount_paise", 0))
        status = row.get("status")
        
        # 1. Flag Duplicate in Settlement
        if ref in seen_refs:
            record_mismatch(db, batch_id, ref, MismatchType.DUPLICATE_IN_SETTLEMENT)
            continue
            
        seen_refs.add(ref)
        
        # Store the settlement record
        settlement = SettlementRecord(
            batch_id=batch_id,
            gateway_ref=ref,
            amount_paise=amt,
            status=status,
            settled_on=datetime.fromisoformat(row.get("settled_on", datetime.now().isoformat()))
        )
        db.add(settlement)
        
        # Match against internal payments
        payment = db.query(Payment).filter(Payment.gateway_ref == ref).first()
        
        # 2. Flag Missing Internally[cite: 1]
        if not payment:
            record_mismatch(db, batch_id, ref, MismatchType.MISSING_INTERNALLY)
            continue
            
        # 3. Flag Amount Mismatch[cite: 1]
        if payment.amount_paise != amt:
            record_mismatch(db, batch_id, ref, MismatchType.AMOUNT_MISMATCH, payment.id)
            
    db.commit()
    return batch_id

def record_mismatch(db: Session, batch_id: str, gateway_ref: str, mismatch_type: MismatchType, payment_id: int = None):
    mismatch = ReconResult(
        batch_id=batch_id,
        gateway_ref=gateway_ref,
        payment_id=payment_id,
        mismatch_type=mismatch_type
    )
    db.add(mismatch)