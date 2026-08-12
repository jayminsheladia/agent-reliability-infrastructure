import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import EventLog
from app.state_text import extract_text

PREVIEW_LENGTH = 200


@dataclass
class TraceStepView:
    step_index: int
    agent_id: str
    input_preview: str
    output_preview: str
    tokens_used: int
    latency_ms: int
    timestamp: datetime
    parent_step_id: uuid.UUID | None
    context_used: list[str]
    event_type: str


def summarize_state(state: dict) -> str:
    """Render a JSONB state column as a short, human-readable preview."""
    text = extract_text(state).strip()
    if len(text) > PREVIEW_LENGTH:
        return text[:PREVIEW_LENGTH] + "…"
    return text


def get_trace(db: Session, run_id: uuid.UUID) -> list[TraceStepView]:
    """The ordered event sequence for a run — the single query both the CLI
    and the web route render from. Ordered by (step_index, timestamp) so a
    Day 6 anomaly marker — which reuses its triggering step's step_index
    rather than claiming a new one — still sorts right after it."""
    events = (
        db.execute(
            select(EventLog)
            .where(EventLog.run_id == run_id)
            .order_by(EventLog.step_index, EventLog.timestamp)
        )
        .scalars()
        .all()
    )
    return [
        TraceStepView(
            step_index=event.step_index,
            agent_id=event.agent_id,
            input_preview=summarize_state(event.input_state),
            output_preview=summarize_state(event.output_state),
            tokens_used=event.tokens_used,
            latency_ms=event.latency_ms,
            timestamp=event.timestamp,
            parent_step_id=event.parent_step_id,
            context_used=(
                event.input_state.get("context_used", [])
                if isinstance(event.input_state, dict)
                else []
            ),
            event_type=event.event_type,
        )
        for event in events
    ]
