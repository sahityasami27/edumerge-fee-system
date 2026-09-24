from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Payment, Charge, LedgerEntry, EntryType
from app.services.ledger import append_ledger_entry

def get_charge_balance(db: Session, charge_id: int) -> int:
    """Calculates the remaining balance of a specific charge from the ledger."""
    result = db.query(
        LedgerEntry.entry_type,
        func.sum(LedgerEntry.amount_paise).label("total")
    ).filter(LedgerEntry.charge_id == charge_id).group_by(LedgerEntry.entry_type).all()
    
    charge_amt = 0
    deductions = 0
    reversals = 0
    
    for entry_type, total in result:
        if total is None:
            continue
        if entry_type == EntryType.CHARGE:
            charge_amt += total
        elif entry_type in (EntryType.PAYMENT_ALLOCATION, EntryType.CONCESSION):
            deductions += total
        elif entry_type == EntryType.REVERSAL:
            reversals += total
            
    return charge_amt - deductions + reversals

def allocate_payment(db: Session, payment: Payment, actor: str):
    # Fetch all charges for the student, ordered by oldest due date then installment number
    charges = db.query(Charge).filter(
        Charge.student_id == payment.student_id
    ).order_by(Charge.due_date.asc(), Charge.installment_no.asc()).all()
    
    remaining_funds = payment.amount_paise
    
    for charge in charges:
        if remaining_funds <= 0:
            break
            
        balance = get_charge_balance(db, charge.id)
        if balance > 0:
            allocation_amount = min(remaining_funds, balance)
            
            append_ledger_entry(
                db=db,
                student_id=payment.student_id,
                entry_type=EntryType.PAYMENT_ALLOCATION,
                amount_paise=allocation_amount,
                actor=actor,
                charge_id=charge.id,
                payment_id=payment.id,
                note=f"Allocation from payment {payment.id}"
            )
            remaining_funds -= allocation_amount

    # Any excess becomes ADVANCE_CREDIT[cite: 1]
    if remaining_funds > 0:
        append_ledger_entry(
            db=db,
            student_id=payment.student_id,
            entry_type=EntryType.ADVANCE_CREDIT,
            amount_paise=remaining_funds,
            actor=actor,
            payment_id=payment.id,
            note=f"Excess payment {payment.id} converted to advance credit"
        )

def reverse_allocations(db: Session, payment: Payment, actor: str):
    """Finds all ledger entries created by a payment and appends reversal entries[cite: 1]."""
    allocations = db.query(LedgerEntry).filter(
        LedgerEntry.payment_id == payment.id,
        LedgerEntry.entry_type.in_([EntryType.PAYMENT_ALLOCATION, EntryType.ADVANCE_CREDIT])
    ).all()
    
    for allocation in allocations:
        append_ledger_entry(
            db=db,
            student_id=allocation.student_id,
            entry_type=EntryType.REVERSAL,
            amount_paise=allocation.amount_paise,
            actor=actor,
            charge_id=allocation.charge_id,
            payment_id=payment.id,
            reverses_entry_id=allocation.id,
            note=f"Reversal of entry {allocation.id}"
        )