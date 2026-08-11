import math
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import cosine_similarity, embed_text
from app.models.event import EventLog
from app.state_text import extract_text

DEFAULT_DECAY_RATE = 0.15


@dataclass
class RetrievedContext:
    event_id: uuid.UUID
    agent_id: str
    step_index: int
    text: str
    score: float


def get_relevant_context(
    db: Session,
    run_id: uuid.UUID,
    requesting_agent_id: str,
    requesting_step_index: int,
    query_or_need: str,
    k: int = 3,
    decay_rate: float = DEFAULT_DECAY_RATE,
) -> list[RetrievedContext]:
    """Return the top-k prior step outputs from this run most relevant to
    what requesting_agent_id needs, ranked by similarity discounted by
    recency: score = similarity * exp(-decay_rate * steps_ago).

    Only looks backward (step_index < requesting_step_index) — an agent
    can't retrieve context from a step that hasn't happened yet.
    """
    candidates = (
        db.execute(
            select(EventLog).where(
                EventLog.run_id == run_id,
                EventLog.step_index < requesting_step_index,
                EventLog.embedding.isnot(None),
            )
        )
        .scalars()
        .all()
    )

    if not candidates:
        return []

    query_embedding = embed_text(query_or_need)

    scored: list[tuple[float, EventLog]] = []
    for event in candidates:
        similarity = cosine_similarity(query_embedding, event.embedding)
        steps_ago = requesting_step_index - event.step_index
        recency = math.exp(-decay_rate * steps_ago)
        scored.append((similarity * recency, event))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    return [
        RetrievedContext(
            event_id=event.id,
            agent_id=event.agent_id,
            step_index=event.step_index,
            text=extract_text(event.output_state),
            score=score,
        )
        for score, event in scored[:k]
    ]
