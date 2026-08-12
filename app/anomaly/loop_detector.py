import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import EventLog


def compute_args_hash(arguments: dict) -> str:
    """Stable hash of tool call arguments — sorted-JSON then sha256, so
    dict key ordering never matters. Assumes arguments don't embed
    non-deterministic values (timestamps, request IDs); a tool that did
    would silently defeat this, since every "repeat" would hash
    differently. Not the case for any tool in this project today."""
    canonical = json.dumps(arguments, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class LoopCheckResult:
    is_loop: bool
    agent_id: str
    tool_name: str
    args_hash: str
    occurrence_count: int
    threshold: int


def check_for_loop(
    db: Session,
    run_id: uuid.UUID,
    agent_id: str,
    tool_name: str,
    arguments: dict,
    threshold: int,
) -> LoopCheckResult:
    """Has (agent_id, tool_name, args_hash) occurred more than `threshold`
    times in this run so far? Re-derives the count from event_log itself
    on every call rather than keeping a separate counter — correct even
    if the loop process restarts mid-run, and trivial cost at this scale.
    """
    args_hash = compute_args_hash(arguments)

    events = (
        db.execute(
            select(EventLog).where(
                EventLog.run_id == run_id,
                EventLog.event_type == "step",
            )
        )
        .scalars()
        .all()
    )

    occurrence_count = 0
    for event in events:
        if event.agent_id != agent_id:
            continue
        for call in event.tool_calls or []:
            if call.get("tool_name") != tool_name:
                continue
            if compute_args_hash(call.get("arguments", {})) == args_hash:
                occurrence_count += 1

    return LoopCheckResult(
        is_loop=occurrence_count > threshold,
        agent_id=agent_id,
        tool_name=tool_name,
        args_hash=args_hash,
        occurrence_count=occurrence_count,
        threshold=threshold,
    )
