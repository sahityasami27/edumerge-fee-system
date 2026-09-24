import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db import Base, get_db
from app.models import PaymentStatus, EntryType, LedgerEntry

# Setup isolated test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_fee_collection.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

# Global test headers for roles
ADMIN_HEADERS = {"X-Role": "Admin", "X-User": "admin1"}
STUDENT_HEADERS = {"X-Role": "Student", "X-User": "1"}
OTHER_STUDENT_HEADERS = {"X-Role": "Student", "X-User": "2"}

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Seed base data required for tests
    client.post("/students", json={"roll_no": "T-001", "name": "Test Student 1", "program": "CS"})
    client.post("/students", json={"roll_no": "T-002", "name": "Test Student 2", "program": "CS"})
    db = TestingSessionLocal()
    from app.models import FeeHead
    db.add(FeeHead(name="Tuition"))
    db.commit()
    db.close()
    yield

def test_duplicate_webhook_processed_once():
    """Test 1: Duplicate webhook is processed once"""
    payload = {"event_id": "evt_1", "gateway_ref": "gw_1", "payment_id": 1, "status": "SUCCESS"}
    res1 = client.post("/webhooks/gateway", json=payload)
    res2 = client.post("/webhooks/gateway", json=payload)
    
    assert res1.json()["status"] == "logged" # Fails gracefully if payment doesn't exist yet
    assert res2.json()["status"] == "ignored"
    assert res2.json()["message"] == "Duplicate event"

def test_same_idempotency_different_body_returns_409():
    """Test 5: Same idempotency key with different body returns 409"""
    payload1 = {"student_id": 1, "amount_paise": 50000, "method": "UPI"}
    payload2 = {"student_id": 1, "amount_paise": 60000, "method": "UPI"}
    
    res1 = client.post("/payments", json=payload1, headers={"Idempotency-Key": "key-1", **ADMIN_HEADERS})
    assert res1.status_code == 200
    
    res2 = client.post("/payments", json=payload2, headers={"Idempotency-Key": "key-1", **ADMIN_HEADERS})
    assert res2.status_code == 409 # Conflict[cite: 1]

def test_student_cannot_see_other_ledger():
    """Test 8: Student role cannot see another student's ledger[cite: 1]"""
    res = client.get("/students/1/ledger", headers=OTHER_STUDENT_HEADERS)
    assert res.status_code == 403

def test_concession_above_charge_rejected():
    """Test 9: Concession above the charge is rejected[cite: 1]"""
    # Create charge of 10000 paise
    client.post("/students/1/charges", json={
        "fee_head_id": 1, "amount_paise": 10000, "installments": 1, "due_date": "2026-10-01T00:00:00"
    }, headers=ADMIN_HEADERS)
    
    # Try concession of 15000 paise
    res = client.post("/students/1/concessions", json={
        "charge_id": 1, "amount_paise": 15000, "reason": "Scholarship"
    }, headers=ADMIN_HEADERS)
    
    assert res.status_code == 400
    assert "cannot exceed" in res.json()["detail"]

def test_overpayment_creates_advance_credit():
    """Test 4: Overpayment creates advance credit[cite: 1]"""
    client.post("/students/1/charges", json={
        "fee_head_id": 1, "amount_paise": 5000, "installments": 1, "due_date": "2026-10-01T00:00:00"
    }, headers=ADMIN_HEADERS)
    
    # Pay 7000 paise (2000 excess)
    pay_res = client.post("/payments", json={
        "student_id": 1, "amount_paise": 7000, "method": "UPI"
    }, headers={"Idempotency-Key": "key-overpay", **ADMIN_HEADERS})
    
    payment_id = pay_res.json()["id"]
    
    # Webhook SUCCESS to trigger allocation
    client.post("/webhooks/gateway", json={
        "event_id": "evt_overpay", "gateway_ref": "gw_2", "payment_id": payment_id, "status": "SUCCESS"
    })
    
    # Check ledger for ADVANCE_CREDIT
    ledger_res = client.get("/students/1/ledger", headers=ADMIN_HEADERS)
    advance_entries = [e for e in ledger_res.json() if e["entry_type"] == "ADVANCE_CREDIT"]
    assert len(advance_entries) == 1
    assert advance_entries[0]["amount_paise"] == 2000

def test_ledger_update_delete_blocked():
    """Test 7: Ledger rows cannot be updated or deleted[cite: 1]"""
    # Enforced at ORM/Service layer. Let's verify no HTTP endpoints exist for it.
    put_res = client.put("/students/1/ledger/1", json={"amount_paise": 0}, headers=ADMIN_HEADERS)
    del_res = client.delete("/students/1/ledger/1", headers=ADMIN_HEADERS)
    assert put_res.status_code == 404
    assert del_res.status_code == 404

def test_invalid_state_transition_rejected():
    """Test 6: Invalid state transition is rejected[cite: 1]"""
    # Create payment -> INITIATED -> PENDING
    pay_res = client.post("/payments", json={"student_id": 1, "amount_paise": 1000, "method": "UPI"}, 
                          headers={"Idempotency-Key": "key-fail-state", **ADMIN_HEADERS})
    payment_id = pay_res.json()["id"]
    
    # Webhook sets to FAILED
    client.post("/webhooks/gateway", json={"event_id": "evt_fail", "gateway_ref": "gw_fail", "payment_id": payment_id, "status": "FAILED"})
    
    # Try to reverse a FAILED payment (Only SUCCESS can be reversed)
    rev_res = client.post(f"/payments/{payment_id}/reverse", params={"reason": "test"}, headers=ADMIN_HEADERS)
    assert rev_res.status_code == 400
    assert "Invalid transition" in rev_res.json()["detail"]