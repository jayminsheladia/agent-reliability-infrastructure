import uuid

from app.db import SessionLocal
from app.embeddings import embed_text
from app.models.event import EventLog
from app.state_text import extract_text


def emit_event(
    *,
    run_id: uuid.UUID,
    agent_id: str,
    step_index: int,
    input_state: dict,
    output_state: dict,
    tool_calls: list[dict],
    tokens_used: int,
    latency_ms: int,
    parent_step_id: uuid.UUID | None,
) -> uuid.UUID:
    """The contract between an agent step and the observability layer.

    Opens its own session and commits immediately, so a step's trace is
    durable the moment it completes — independent of whatever happens
    later in the run.
    """
    text_for_embedding = extract_text(output_state)
    embedding = embed_text(text_for_embedding) if text_for_embedding else None

    db = SessionLocal()
    try:
        event = EventLog(
            id=uuid.uuid4(),
            run_id=run_id,
            agent_id=agent_id,
            step_index=step_index,
            input_state=input_state,
            output_state=output_state,
            tool_calls=tool_calls,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            parent_step_id=parent_step_id,
            embedding=embedding,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event.id
    finally:
        db.close()
