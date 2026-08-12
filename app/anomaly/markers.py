import uuid

from app.events import emit_event


def write_anomaly_marker(
    *,
    run_id: uuid.UUID,
    step_index: int,
    triggering_agent_id: str,
    parent_step_id: uuid.UUID | None,
    event_type: str,
    detector_name: str,
    reason: str,
    details: dict,
) -> uuid.UUID:
    """Write a marker row into event_log recording that a detector fired.

    Shared plumbing for both detectors — not detection logic itself, just
    "how do we record that one fired," so loop_detector.py and
    cost_detector.py stay independent of each other. Reuses the
    triggering step's own step_index (not a new one) so it can't collide
    with whatever step_index the run assigns next; the trace viewer
    orders by (step_index, timestamp) so the marker still reliably sorts
    right after the step that caused it.
    """
    return emit_event(
        run_id=run_id,
        agent_id=detector_name,
        step_index=step_index,
        input_state={"text": f"triggered by {triggering_agent_id}'s step"},
        output_state={"text": reason, "details": details},
        tool_calls=[],
        tokens_used=0,
        latency_ms=0,
        parent_step_id=parent_step_id,
        event_type=event_type,
    )
