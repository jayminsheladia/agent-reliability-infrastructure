import json
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import redis

from app.config import settings

_redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)

PENDING_SET_KEY = "approvals:pending"


@dataclass
class PendingApproval:
    id: str
    run_id: str
    step_index: int
    agent_id: str
    tool_name: str
    arguments: dict
    status: str  # "pending" | "approved" | "rejected"
    created_at: str


def _key(approval_id: str) -> str:
    return f"approval:{approval_id}"


def _save(approval: PendingApproval) -> None:
    _redis.set(_key(approval.id), json.dumps(asdict(approval)))


def create_approval(
    run_id: uuid.UUID, step_index: int, agent_id: str, tool_name: str, arguments: dict
) -> PendingApproval:
    approval = PendingApproval(
        id=str(uuid.uuid4()),
        run_id=str(run_id),
        step_index=step_index,
        agent_id=agent_id,
        tool_name=tool_name,
        arguments=arguments,
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _save(approval)
    _redis.sadd(PENDING_SET_KEY, approval.id)
    return approval


def get_approval(approval_id: str) -> PendingApproval | None:
    raw = _redis.get(_key(approval_id))
    if raw is None:
        return None
    return PendingApproval(**json.loads(raw))


def list_pending() -> list[PendingApproval]:
    ids = _redis.smembers(PENDING_SET_KEY)
    approvals = (get_approval(approval_id) for approval_id in ids)
    return [a for a in approvals if a is not None and a.status == "pending"]


def resolve_approval(approval_id: str, status: str) -> PendingApproval | None:
    approval = get_approval(approval_id)
    if approval is None:
        return None
    approval.status = status
    _save(approval)
    _redis.srem(PENDING_SET_KEY, approval.id)
    return approval


def wait_for_resolution(
    approval_id: str, poll_interval_seconds: float = 1.0, timeout_seconds: float = 300.0
) -> PendingApproval:
    """Block the caller until the approval is resolved (approved/rejected).

    This is the resume half of the pause/resume mechanism: the agent loop
    process calls this and polls Redis, which any process — including the
    FastAPI server handling the approve/reject click — can update.
    """
    elapsed = 0.0
    while True:
        approval = get_approval(approval_id)
        if approval is None:
            raise RuntimeError(f"approval {approval_id} disappeared from the queue")
        if approval.status != "pending":
            return approval
        if elapsed >= timeout_seconds:
            raise TimeoutError(f"approval {approval_id} was not resolved within {timeout_seconds}s")
        time.sleep(poll_interval_seconds)
        elapsed += poll_interval_seconds
