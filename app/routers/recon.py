from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import ReconResult, AuditLog
from app.services.reconciliation import process_settlement_csv
from app.deps import require_admin_or_accountant

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])

@router.post("/upload")
async def upload_settlement(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin_or_accountant) # Reconciliations require accountant/admin[cite: 1]
):
    contents = await file.read()
    batch_id = process_settlement_csv(db, contents)
    return {"status": "success", "batch_id": batch_id}

@router.get("/results")
def get_recon_results(
    batch_id: str = None, 
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin_or_accountant)
):
    query = db.query(ReconResult).filter(ReconResult.resolved == False)
    if batch_id:
        query = query.filter(ReconResult.batch_id == batch_id)
    return query.all()

@router.post("/results/{result_id}/resolve")
def resolve_mismatch(
    result_id: int, 
    note: str, 
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin_or_accountant)
):
    mismatch = db.query(ReconResult).filter(ReconResult.id == result_id).first()
    if not mismatch:
        raise HTTPException(status_code=404, detail="Mismatch not found")
        
    mismatch.resolved = True
    mismatch.resolution_note = note
    
    # Audit log for manual resolution[cite: 1]
    audit = AuditLog(
        actor=user["user"], role=user["role"], action="RESOLVE_RECON_MISMATCH",
        entity="ReconResult", entity_id=mismatch.id,
        after_json={"note": note, "resolved": True}
    )
    db.add(audit)
    db.commit()
    return {"status": "resolved"}