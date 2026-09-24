import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal, Base, engine
from app.models import Student, FeeHead

def seed_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Check if already seeded
    if db.query(FeeHead).first():
        print("Database already seeded.")
        db.close()
        return

    # 1. Seed Fee Heads
    fee_heads = [
        FeeHead(name="Tuition"),
        FeeHead(name="Hostel"),
        FeeHead(name="Transport"),
        FeeHead(name="Exam")
    ]
    db.add_all(fee_heads)
    
    # 2. Seed a Student
    student = Student(
        roll_no="CS2026-001",
        name="Alice Smith",
        program="Computer Science"
    )
    db.add(student)
    
    db.commit()
    print("Seed data inserted successfully.")
    db.close()

if __name__ == "__main__":
    seed_data()