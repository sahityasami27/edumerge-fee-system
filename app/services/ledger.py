from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import LedgerEntry, EntryType, Charge, AuditLog
from fastapi import HTTPException
from datetime import datetime, timezone

def append_ledger_entry(
    db: Session, 
    student_id: int, 
    entry_type: EntryType, 
    amount_paise: int, 
    actor: str,
    charge_id: int = None, 
    payment_id: int = None,
    reverses_entry_id: int = None,
    note: str = None
) -> LedgerEntry:
    # Deliberately enforces append-only by exposing no update/delete methods
    entry = LedgerEntry(
        student_id=student_id,
        charge_id=charge_id,
        payment_id=payment_id,
        entry_type=entry_type,
        amount_paise=amount_paise,
        reverses_entry_id=reverses_entry_id,
        note=note,
        created_by=actor
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

def create_charges(
    db: Session, 
    student_id: int, 
    fee_head_id: int, 
    total_amount_paise: int, 
    installments: int, 
    due_date: datetime, 
    actor: str
) -> list[Charge]:
    created_charges = []
    base_amount = total_amount_paise // installments
    remainder = total_amount_paise % installments

    for i in range(1, installments + 1):
        # Distribute any remainder paise to the first installment
        installment_amount = base_amount + (remainder if i == 1 else 0)
        
        charge = Charge(
            student_id=student_id,
            fee_head_id=fee_head_id,
            installment_no=i,
            amount_paise=installment_amount,
            due_date=due_date
        )
        db.add(charge)
        db.commit()
        db.refresh(charge)
        created_charges.append(charge)

        append_ledger_entry(
            db=db,
            student_id=student_id,
            charge_id=charge.id,
            entry_type=EntryType.CHARGE,
            amount_paise=installment_amount, # Positive impact on balance
            actor=actor,
            note=f"Charge generated: Installment {i}/{installments}"
        )
    return created_charges

def apply_concession(
    db: Session, 
    student_id: int, 
    charge_id: int, 
    amount_paise: int, 
    reason: str, 
    actor: str
) -> LedgerEntry:
    charge = db.query(Charge).filter(Charge.id == charge_id, Charge.student_id == student_id).first()
    if not charge:
        raise HTTPException(status_code=404, detail="Charge not found")
    
    if amount_paise > charge.amount_paise:
        raise HTTPException(status_code=400, detail="Concession cannot exceed charge amount")

    # Log the concession action for audit[cite: 1]
    audit = AuditLog(
        actor=actor, role="Admin", action="GRANT_CONCESSION", 
        entity="Charge", entity_id=charge.id, 
        after_json={"amount_paise": amount_paise, "reason": reason}
    )
    db.add(audit)

    return append_ledger_entry(
        db=db,
        student_id=student_id,
        charge_id=charge_id,
        entry_type=EntryType.CONCESSION,
        amount_paise=amount_paise, # Negative impact on balance
        actor=actor,
        note=f"Concession: {reason}"
    )

def calculate_student_outstanding(db: Session, student_id: int) -> int:
    result = db.query(
        LedgerEntry.entry_type,
        func.sum(LedgerEntry.amount_paise).label("total")
    ).filter(LedgerEntry.student_id == student_id).group_by(LedgerEntry.entry_type).all()
    
    balance = 0
    for entry_type, total in result:
        if total is None:
            continue
        if entry_type == EntryType.CHARGE:
            balance += total
        elif entry_type in [EntryType.PAYMENT_ALLOCATION, EntryType.CONCESSION]:
            balance -= total
        elif entry_type == EntryType.REVERSAL:
            balance += total # Reversals add back to the outstanding[cite: 1]
        elif entry_type == EntryType.ADVANCE_CREDIT:
            balance -= total

    return balance