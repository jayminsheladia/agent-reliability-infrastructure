import sys
import uuid

from app.anomaly.cost_detector import check_agent_zscore, check_hard_threshold
from app.anomaly.loop_detector import check_for_loop
from app.anomaly.markers import write_anomaly_marker
from app.approvals.gate import propose_and_run_tool_call
from app.config import settings
from app.db import SessionLocal
from app.events import emit_event
from app.llm import call_llm
from app.retrieval import get_relevant_context

# (agent_id, prompt_template, need, k) — need=None means "no retrieval, use
# the raw prior context directly" (only true for the first step, which has
# no prior events to retrieve from). k is how many prior events to pull in;
# reviewer uses k=1 deliberately so retrieval visibly picks one candidate
# over the other rather than just re-ranking everything available.
LLM_STEPS = [
    ("researcher", "Research the topic below and list 3-5 key facts.\n\nTopic: {context}", None, None),
    (
        "drafter",
        "Using this research, write a short draft paragraph.\n\nResearch:\n{context}",
        "research findings and key facts about the topic",
        3,
    ),
    (
        "reviewer",
        "Review this draft and give brief, actionable feedback.\n\nDraft:\n{context}",
        "the draft content and any research findings related to it",
        1,
    ),
]

# (agent_id, tool_name, build_arguments) — deterministic placeholder tool calls
# that exercise the policy gate: notifier always requires approval (Day 1's
# unconditional send_email rule), executor requires approval conditionally
# (amount > 100). Unaffected by Day 5's retrieval work — still receive the
# raw immediately-prior step's output, same as Day 4.
TOOL_STEPS = [
    ("notifier", "send_email", lambda context: {"to": "team@example.com", "body": context}),
    ("executor", "execute_action", lambda context: {"action_type": "archive_run", "amount": 250}),
]


class RunKilledError(Exception):
    """Raised internally when a detector kills the run (loop detection is
    the only kill-worthy trigger today). Caught once in run_pipeline() so
    the run stops cleanly instead of crashing with a traceback."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _check_cost_anomalies(run_id, agent_id, step_index, parent_step_id, tokens_used) -> None:
    """Flag-only: writes a marker on either trigger, never halts the run."""
    db = SessionLocal()
    try:
        hard = check_hard_threshold(db, run_id, settings.cost_hard_threshold_tokens)
        if hard.is_anomaly:
            write_anomaly_marker(
                run_id=run_id,
                step_index=step_index,
                triggering_agent_id=agent_id,
                parent_step_id=parent_step_id,
                event_type="cost_anomaly",
                detector_name="cost_detector",
                reason=hard.reason,
                details={
                    "trigger": "hard_threshold",
                    "current_value": hard.current_value,
                    "threshold": hard.threshold,
                },
            )
            print(f"[cost_detector] {hard.reason}")

        zscore = check_agent_zscore(
            db,
            agent_id,
            run_id,
            tokens_used,
            z_threshold=settings.cost_zscore_threshold,
            min_samples=settings.cost_zscore_min_samples,
        )
        if zscore.is_anomaly:
            write_anomaly_marker(
                run_id=run_id,
                step_index=step_index,
                triggering_agent_id=agent_id,
                parent_step_id=parent_step_id,
                event_type="cost_anomaly",
                detector_name="cost_detector",
                reason=zscore.reason,
                details={
                    "trigger": "zscore",
                    "z_score": zscore.z_score,
                    "mean": zscore.mean,
                    "stddev": zscore.stddev,
                },
            )
            print(f"[cost_detector] {zscore.reason}")
    finally:
        db.close()


def _check_loop(run_id, agent_id, step_index, parent_step_id, tool_name, arguments) -> None:
    """Kill-worthy: writes a marker and raises RunKilledError if triggered."""
    db = SessionLocal()
    try:
        result = check_for_loop(db, run_id, agent_id, tool_name, arguments, threshold=settings.loop_threshold)
    finally:
        db.close()

    if result.is_loop:
        reason = (
            f"{agent_id} called {tool_name} with identical arguments "
            f"{result.occurrence_count} times (threshold={result.threshold})"
        )
        write_anomaly_marker(
            run_id=run_id,
            step_index=step_index,
            triggering_agent_id=agent_id,
            parent_step_id=parent_step_id,
            event_type="loop_detected",
            detector_name="loop_detector",
            reason=reason,
            details={
                "tool_name": tool_name,
                "args_hash": result.args_hash,
                "occurrence_count": result.occurrence_count,
                "threshold": result.threshold,
            },
        )
        raise RunKilledError(reason)


def run_pipeline(topic: str) -> uuid.UUID:
    run_id = uuid.uuid4()
    parent_step_id: uuid.UUID | None = None
    context = topic
    step_index = 0

    try:
        for agent_id, prompt_template, need, k in LLM_STEPS:
            if need is None:
                context_text = context
                context_used_ids: list[str] = []
            else:
                db = SessionLocal()
                try:
                    retrieved = get_relevant_context(db, run_id, agent_id, step_index, need, k=k)
                finally:
                    db.close()
                context_text = "\n\n".join(f"[{r.agent_id} step {r.step_index}]: {r.text}" for r in retrieved)
                context_used_ids = [str(r.event_id) for r in retrieved]

            prompt = prompt_template.format(context=context_text)
            input_state = {"text": context_text, "context_used": context_used_ids}

            result = call_llm(prompt)
            output_state = {"text": result.text}

            parent_step_id = emit_event(
                run_id=run_id,
                agent_id=agent_id,
                step_index=step_index,
                input_state=input_state,
                output_state=output_state,
                tool_calls=[],
                tokens_used=result.tokens_used,
                latency_ms=result.latency_ms,
                parent_step_id=parent_step_id,
            )
            _check_cost_anomalies(run_id, agent_id, step_index, parent_step_id, result.tokens_used)

            context = result.text
            step_index += 1

        for agent_id, tool_name, build_arguments in TOOL_STEPS:
            arguments = build_arguments(context)
            input_state = {"text": context}

            outcome = propose_and_run_tool_call(run_id, step_index, agent_id, tool_name, arguments)
            output_state = {"text": outcome["result_text"]}

            parent_step_id = emit_event(
                run_id=run_id,
                agent_id=agent_id,
                step_index=step_index,
                input_state=input_state,
                output_state=output_state,
                tool_calls=[outcome["tool_call_record"]],
                tokens_used=0,
                latency_ms=outcome["latency_ms"],
                parent_step_id=parent_step_id,
            )
            _check_loop(run_id, agent_id, step_index, parent_step_id, tool_name, arguments)
            _check_cost_anomalies(run_id, agent_id, step_index, parent_step_id, 0)

            context = outcome["result_text"]
            step_index += 1
    except RunKilledError as e:
        print(f"[agent_loop] RUN KILLED: {e.reason}")

    return run_id


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]) or "the benefits of local-first software"
    run_id = run_pipeline(topic)
    print(f"run_id={run_id}")
