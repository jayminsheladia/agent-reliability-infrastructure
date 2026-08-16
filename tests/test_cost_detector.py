import uuid

from app.anomaly.cost_detector import check_agent_zscore, check_hard_threshold
from app.events import emit_event


def _emit_llm_step(run_id, step_index, agent_id, tokens_used):
    emit_event(
        run_id=run_id,
        agent_id=agent_id,
        step_index=step_index,
        input_state={},
        output_state={"text": "x"},
        tool_calls=[],
        tokens_used=tokens_used,
        latency_ms=0,
        parent_step_id=None,
    )


def test_hard_threshold_fires_when_cumulative_exceeds_limit(db):
    run_id = uuid.uuid4()
    for i in range(3):
        _emit_llm_step(run_id, i, "researcher", 2000)

    result = check_hard_threshold(db, run_id, threshold_tokens=5000)

    assert result.is_anomaly is True
    assert result.current_value == 6000


def test_hard_threshold_does_not_fire_under_limit(db):
    run_id = uuid.uuid4()
    _emit_llm_step(run_id, 0, "researcher", 100)

    result = check_hard_threshold(db, run_id, threshold_tokens=5000)

    assert result.is_anomaly is False


def test_zscore_fires_on_outlier_with_sufficient_history(db):
    agent_id = "researcher"
    # Seed 3 historical runs with tight variance around 42 tokens.
    for tokens in (40, 42, 44):
        _emit_llm_step(uuid.uuid4(), 0, agent_id, tokens)

    result = check_agent_zscore(
        db, agent_id, uuid.uuid4(), current_step_tokens=5000, z_threshold=2.0, min_samples=3
    )

    assert result.is_anomaly is True


def test_zscore_skips_when_insufficient_history(db):
    agent_id = f"agent-{uuid.uuid4()}"  # guaranteed to have no prior rows

    result = check_agent_zscore(
        db, agent_id, uuid.uuid4(), current_step_tokens=5000, z_threshold=2.0, min_samples=3
    )

    assert result.is_anomaly is False
    assert "insufficient history" in result.reason


def test_zscore_excludes_current_run_from_baseline(db):
    agent_id = "researcher"
    run_id = uuid.uuid4()
    # All "history" is actually from the current run — should not count.
    for tokens in (40, 42, 44):
        _emit_llm_step(run_id, 0, agent_id, tokens)

    result = check_agent_zscore(
        db, agent_id, run_id, current_step_tokens=5000, z_threshold=2.0, min_samples=3
    )

    assert result.is_anomaly is False
    assert "insufficient history" in result.reason
