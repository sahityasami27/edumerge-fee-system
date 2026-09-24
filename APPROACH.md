# Approach & Architecture

## Assumptions
* Single institution operations in INR only.
* Money is stored strictly as integer paise to prevent floating-point inaccuracies.
* System operates 24x7 without business calendar restrictions.
* Payment gateway is mocked via webhook endpoints.
* Header-based roles (`X-Role`, `X-User`) are used in lieu of full authentication.
* SQLite is used for zero-setup evaluation, but the SQLAlchemy models are fully Postgres-compatible.
* Refunds to the bank are handled out-of-band; the system only marks the internal reversal.
* Payment allocation applies to the oldest due date first, followed by the installment number.

## Architectural Decisions
1. **Append-Only Ledger:** The system strictly prohibits `UPDATE` and `DELETE` operations on ledger entries to ensure absolute financial compliance and auditability. State changes (like concessions or reversals) are appended as new transactional rows.
2. **Derived State:** Outstanding balances are never stored in a static database column. They are dynamically aggregated from the ledger history to guarantee absolute consistency between transaction logs and current balances.
3. **Centralized State Machine:** Payment status transitions are governed by a single, centralized dictionary mapping allowed states (`INITIATED` -> `PENDING` -> `SUCCESS` / `FAILED`), preventing illegal transitions like reversing an already failed payment.
4. **Idempotency:** Payment endpoints require an `Idempotency-Key` header. Retrying with the same payload returns the existing payment safely, while altering the payload throws a 409 Conflict.
