import sys
import uuid

from app.approvals.gate import propose_and_run_tool_call
from app.events import emit_event
from app.llm import call_llm

LLM_STEPS = [
    ("researcher", "Research the topic below and list 3-5 key facts.\n\nTopic: {context}"),
    ("drafter", "Using this research, write a short draft paragraph.\n\nResearch:\n{context}"),
    ("reviewer", "Review this draft and give brief, actionable feedback.\n\nDraft:\n{context}"),
]

# (agent_id, tool_name, build_arguments) — deterministic placeholder tool calls
# that exercise the policy gate: notifier always requires approval (Day 1's
# unconditional send_email rule), executor requires approval conditionally
# (amount > 100).
TOOL_STEPS = [
    ("notifier", "send_email", lambda context: {"to": "team@example.com", "body": context}),
    ("executor", "execute_action", lambda context: {"action_type": "archive_run", "amount": 250}),
]


def run_pipeline(topic: str) -> uuid.UUID:
    run_id = uuid.uuid4()
    parent_step_id: uuid.UUID | None = None
    context = topic
    step_index = 0

    for agent_id, prompt_template in LLM_STEPS:
        prompt = prompt_template.format(context=context)
        input_state = {"text": context}

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
        context = outcome["result_text"]
        step_index += 1

    return run_id


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]) or "the benefits of local-first software"
    run_id = run_pipeline(topic)
    print(f"run_id={run_id}")
