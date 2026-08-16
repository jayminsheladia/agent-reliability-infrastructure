import uuid

from app.events import emit_event
from app.models.event import EventLog


def test_emit_event_writes_row_with_expected_fields(db):
    run_id = uuid.uuid4()

    event_id = emit_event(
        run_id=run_id,
        agent_id="tester",
        step_index=0,
        input_state={"text": "input"},
        output_state={"text": "output"},
        tool_calls=[],
        tokens_used=10,
        latency_ms=5,
        parent_step_id=None,
    )

    row = db.query(EventLog).filter_by(id=event_id).one()
    assert row.run_id == run_id
    assert row.agent_id == "tester"
    assert row.step_index == 0
    assert row.input_state == {"text": "input"}
    assert row.output_state == {"text": "output"}
    assert row.tokens_used == 10
    assert row.latency_ms == 5
    assert row.event_type == "step"
    assert row.parent_step_id is None
    assert row.embedding is not None  # Day 5: embedded on write


def test_emit_event_chains_parent_step_id(db):
    run_id = uuid.uuid4()
    first_id = emit_event(
        run_id=run_id,
        agent_id="a",
        step_index=0,
        input_state={},
        output_state={"text": "x"},
        tool_calls=[],
        tokens_used=0,
        latency_ms=0,
        parent_step_id=None,
    )
    second_id = emit_event(
        run_id=run_id,
        agent_id="b",
        step_index=1,
        input_state={},
        output_state={"text": "y"},
        tool_calls=[],
        tokens_used=0,
        latency_ms=0,
        parent_step_id=first_id,
    )

    row = db.query(EventLog).filter_by(id=second_id).one()
    assert row.parent_step_id == first_id


def test_emit_event_defaults_to_step_event_type_but_accepts_override(db):
    run_id = uuid.uuid4()
    event_id = emit_event(
        run_id=run_id,
        agent_id="loop_detector",
        step_index=0,
        input_state={},
        output_state={"text": "flagged"},
        tool_calls=[],
        tokens_used=0,
        latency_ms=0,
        parent_step_id=None,
        event_type="loop_detected",
    )

    row = db.query(EventLog).filter_by(id=event_id).one()
    assert row.event_type == "loop_detected"
