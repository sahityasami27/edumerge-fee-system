from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Student, LedgerEntry, ReconResult
from app.services.ledger import calculate_student_outstanding

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/ui/ledger/{student_id}", response_class=HTMLResponse)
def view_ledger(request: Request, student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    entries = db.query(LedgerEntry).filter(LedgerEntry.student_id == student_id).order_by(LedgerEntry.created_at.asc()).all()
    balance = calculate_student_outstanding(db, student_id)
    return templates.TemplateResponse("ledger.html", {
        "request": request, 
        "student": student, 
        "entries": entries, 
        "balance": balance
    })

@router.get("/ui/outstanding", response_class=HTMLResponse)
def view_outstanding(request: Request, db: Session = Depends(get_db)):
    students = db.query(Student).all()
    report = []
    for s in students:
        bal = calculate_student_outstanding(db, s.id)
        if bal > 0:
            report.append({"student": s, "balance": bal})
    return templates.TemplateResponse("outstanding.html", {"request": request, "report": report})

@router.get("/ui/reconciliation", response_class=HTMLResponse)
def view_reconciliation(request: Request, db: Session = Depends(get_db)):
    mismatches = db.query(ReconResult).filter(ReconResult.resolved == False).all()
    return templates.TemplateResponse("reconciliation.html", {"request": request, "mismatches": mismatches})