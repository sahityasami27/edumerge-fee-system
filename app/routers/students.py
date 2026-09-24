from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from app.db import get_db
from app.models import Student, LedgerEntry
from app.schemas import LedgerEntryResponse, OutstandingResponse
from app.services.ledger import calculate_student_outstanding
from app.deps import get_current_user_role

router = APIRouter(prefix="/students", tags=["students"])

class StudentCreate(BaseModel):
    roll_no: str
    name: str
    program: str

@router.post("")
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    student = Student(**payload.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student

@router.get("/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

@router.get("/{student_id}/ledger", response_model=List[LedgerEntryResponse])
def get_student_ledger(
    student_id: int, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_role)
):
    # Enforce role isolation: Students can only view their own ledger
    if user["role"] == "Student" and str(student_id) != user["user"]:
        raise HTTPException(status_code=403, detail="Cannot view another student's ledger")
        
    entries = db.query(LedgerEntry).filter(
        LedgerEntry.student_id == student_id
    ).order_by(LedgerEntry.created_at.asc()).all()
    return entries

@router.get("/{student_id}/outstanding", response_model=OutstandingResponse)
def get_student_outstanding(
    student_id: int, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_role)
):
    if user["role"] == "Student" and str(student_id) != user["user"]:
        raise HTTPException(status_code=403, detail="Cannot view another student's data")
        
    # Outstanding is computed dynamically from the ledger
    balance = calculate_student_outstanding(db, student_id)
    return OutstandingResponse(student_id=student_id, total_outstanding_paise=balance)