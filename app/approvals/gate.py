import time
import uuid

from app.approvals import queue
from app.policy import evaluate_policy
from app.tools import TOOLS

POLL_INTERVAL_SECONDS = 1.0
APPROVAL_TIMEOUT_SECONDS = 300.0


def propose_and_run_tool_call(
    run_id: uuid.UUID, step_index: int, agent_id: str, tool_name: str, arguments: dict
) -> dict:
    """The gating mechanism: check the tool call against policy, block on
    human approval if required, then execute (or skip, if rejected).

    Returns {"tool_call_record": ..., "result_text": ..., "latency_ms": ...}
    for the caller to fold into that step's emit_event() call.
    """
    start = time.perf_counter()

    if evaluate_policy(tool_name, arguments):
        approval = queue.create_approval(run_id, step_index, agent_id, tool_name, arguments)
        print(f"[{agent_id}] {tool_name} requires approval -> pending as {approval.id}. Waiting...")

        resolved = queue.wait_for_resolution(
            approval.id, POLL_INTERVAL_SECONDS, APPROVAL_TIMEOUT_SECONDS
        )

        if resolved.status == "approved":
            result_text = TOOLS[tool_name](**arguments)
            status = "executed"
        else:
            result_text = f"Tool call rejected (approval_id={resolved.id})"
            status = "rejected"

        record = {
            "tool_name": tool_name,
            "arguments": arguments,
            "status": status,
            "approval_id": resolved.id,
        }
    else:
        result_text = TOOLS[tool_name](**arguments)
        record = {
            "tool_name": tool_name,
            "arguments": arguments,
            "status": "executed",
            "approval_id": None,
        }

    latency_ms = int((time.perf_counter() - start) * 1000)
    return {"tool_call_record": record, "result_text": result_text, "latency_ms": latency_ms}
