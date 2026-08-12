import statistics
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.event import EventLog


@dataclass
class CostAnomalyResult:
    is_anomaly: bool
    reason: str
    current_value: float
    threshold: float | None = None
    mean: float | None = None
    stddev: float | None = None
    z_score: float | None = None


def check_hard_threshold(db: Session, run_id: uuid.UUID, threshold_tokens: int) -> CostAnomalyResult:
    """Flag if cumulative tokens_used across this run's steps so far
    exceeds a fixed configurable limit."""
    cumulative = db.execute(
        select(func.coalesce(func.sum(EventLog.tokens_used), 0)).where(
            EventLog.run_id == run_id,
            EventLog.event_type == "step",
        )
    ).scalar_one()

    is_anomaly = cumulative > threshold_tokens
    reason = (
        f"cumulative tokens_used={cumulative} exceeds threshold={threshold_tokens}"
        if is_anomaly
        else "within threshold"
    )
    return CostAnomalyResult(
        is_anomaly=is_anomaly,
        reason=reason,
        current_value=cumulative,
        threshold=threshold_tokens,
    )


def check_agent_zscore(
    db: Session,
    agent_id: str,
    run_id: uuid.UUID,
    current_step_tokens: int,
    z_threshold: float,
    min_samples: int,
) -> CostAnomalyResult:
    """Flag if this agent's token usage in the current step deviates more
    than z_threshold standard deviations from that agent's historical
    average across all past runs. Excludes the current run (comparing
    against itself would be meaningless) and marker rows (tokens_used=0,
    which would corrupt the baseline)."""
    history = (
        db.execute(
            select(EventLog.tokens_used).where(
                EventLog.agent_id == agent_id,
                EventLog.run_id != run_id,
                EventLog.event_type == "step",
            )
        )
        .scalars()
        .all()
    )

    if len(history) < min_samples:
        return CostAnomalyResult(
            is_anomaly=False,
            reason=f"insufficient history for {agent_id} ({len(history)} < {min_samples} samples)",
            current_value=current_step_tokens,
        )

    mean = statistics.mean(history)
    stddev = statistics.stdev(history)

    if stddev == 0:
        return CostAnomalyResult(
            is_anomaly=False,
            reason=f"no variance in {agent_id}'s history (stddev=0)",
            current_value=current_step_tokens,
            mean=mean,
            stddev=0.0,
        )

    z_score = (current_step_tokens - mean) / stddev
    is_anomaly = abs(z_score) > z_threshold
    reason = (
        f"{agent_id}'s tokens_used={current_step_tokens} is {z_score:.2f} std devs from "
        f"its historical mean={mean:.1f} (stddev={stddev:.1f}, threshold={z_threshold})"
        if is_anomaly
        else "within normal range"
    )
    return CostAnomalyResult(
        is_anomaly=is_anomaly,
        reason=reason,
        current_value=current_step_tokens,
        mean=mean,
        stddev=stddev,
        z_score=z_score,
    )
