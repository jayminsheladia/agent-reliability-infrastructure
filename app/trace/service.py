import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import EventLog

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


def summarize_state(state: dict) -> str:
    """Render a JSONB state column as a short, human-readable preview."""
    if not state:
        return ""

    if isinstance(state, dict) and isinstance(state.get("text"), str):
        text = state["text"]
    else:
        text = json.dumps(state, separators=(",", ":"))

    text = text.strip()
    if len(text) > PREVIEW_LENGTH:
        return text[:PREVIEW_LENGTH] + "…"
    return text


def get_trace(db: Session, run_id: uuid.UUID) -> list[TraceStepView]:
    """The ordered event sequence for a run — the single query both the CLI
    and the web route render from."""
    events = (
        db.execute(
            select(EventLog).where(EventLog.run_id == run_id).order_by(EventLog.step_index)
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
        )
        for event in events
    ]
