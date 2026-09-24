from fastapi import FastAPI
from app.db import engine, Base
import app.models as models
from app.routers import payments, webhooks, charges, students, recon, ui

# Initialize database schemas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Edumerge Fee System")

# Register API routers
app.include_router(students.router)
app.include_router(payments.router)
app.include_router(webhooks.router)
app.include_router(charges.router)
app.include_router(recon.router)

# Register UI router
app.include_router(ui.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}