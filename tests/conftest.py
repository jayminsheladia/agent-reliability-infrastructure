import pytest

from app.db import SessionLocal
from app.models.event import EventLog


@pytest.fixture
def db():
    """These are integration tests against the real Postgres instance
    (docker compose up) — this project doesn't mock the DB layer, so the
    tests don't either."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_event_log(db):
    """Every test starts and ends with an empty event_log, so tests can't
    contaminate each other's history (this matters especially for the
    cost z-score tests, which key off an agent's historical average)."""
    db.query(EventLog).delete()
    db.commit()
    yield
    db.query(EventLog).delete()
    db.commit()
