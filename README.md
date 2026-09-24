# Edumerge Fee Collection & Reconciliation System

A robust API and lightweight UI for fee management, built with FastAPI and SQLAlchemy.

## Quick Start (Docker)
1. Run `docker-compose up --build`
2. Open http://localhost:8000/docs for the API Swagger UI.
3. Open http://localhost:8000/ui/outstanding for the UI.

## Local Setup (Without Docker)
1. Create a virtual environment and install dependencies: `pip install -r requirements.txt`
2. Seed the database: `python tests/seed.py`
3. Start the server: `uvicorn app.main:app --reload`
4. Run tests: `pytest tests/ -v`

## Technology Stack
* Python 3.12+, FastAPI, Pydantic v2
* SQLAlchemy 2.0 with SQLite (Postgres-ready)
* Jinja2 + HTMX + Tailwind CSS for UI
