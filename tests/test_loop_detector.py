import uuid

from app.anomaly.loop_detector import check_for_loop, compute_args_hash
from app.events import emit_event


def test_compute_args_hash_stable_regardless_of_key_order():
    assert compute_args_hash({"a": 1, "b": 2}) == compute_args_hash({"b": 2, "a": 1})


def test_compute_args_hash_differs_for_different_args():
    assert compute_args_hash({"a": 1}) != compute_args_hash({"a": 2})


def _emit_tool_call(run_id, step_index, agent_id, tool_name, arguments):
    emit_event(
        run_id=run_id,
        agent_id=agent_id,
        step_index=step_index,
        input_state={},
        output_state={"text": "done"},
        tool_calls=[{"tool_name": tool_name, "arguments": arguments, "status": "executed", "approval_id": None}],
        tokens_used=0,
        latency_ms=0,
        parent_step_id=None,
    )


def test_check_for_loop_fires_past_threshold(db):
    run_id = uuid.uuid4()
    arguments = {"action_type": "ping", "amount": 10}

    result = None
    for i in range(5):  # threshold=3 means the 4th occurrence trips it
        _emit_tool_call(run_id, i, "looper", "execute_action", arguments)
        result = check_for_loop(db, run_id, "looper", "execute_action", arguments, threshold=3)

    assert result.is_loop is True
    assert result.occurrence_count == 5


def test_check_for_loop_does_not_fire_under_threshold(db):
    run_id = uuid.uuid4()
    arguments = {"action_type": "ping", "amount": 10}

    _emit_tool_call(run_id, 0, "looper", "execute_action", arguments)
    result = check_for_loop(db, run_id, "looper", "execute_action", arguments, threshold=3)

    assert result.is_loop is False


def test_check_for_loop_ignores_different_agent(db):
    run_id = uuid.uuid4()
    arguments = {"action_type": "ping", "amount": 10}

    for i in range(5):
        _emit_tool_call(run_id, i, "agent_a", "execute_action", arguments)

    # Same tool+args, but a different agent — shouldn't count toward agent_b's loop.
    result = check_for_loop(db, run_id, "agent_b", "execute_action", arguments, threshold=3)
    assert result.is_loop is False
