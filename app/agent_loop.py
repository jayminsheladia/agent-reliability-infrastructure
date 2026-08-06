import sys
import uuid

from app.events import emit_event
from app.llm import call_llm

STEPS = [
    ("researcher", "Research the topic below and list 3-5 key facts.\n\nTopic: {context}"),
    ("drafter", "Using this research, write a short draft paragraph.\n\nResearch:\n{context}"),
    ("reviewer", "Review this draft and give brief, actionable feedback.\n\nDraft:\n{context}"),
]


def run_pipeline(topic: str) -> uuid.UUID:
    run_id = uuid.uuid4()
    parent_step_id: uuid.UUID | None = None
    context = topic

    for step_index, (agent_id, prompt_template) in enumerate(STEPS):
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

    return run_id


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]) or "the benefits of local-first software"
    run_id = run_pipeline(topic)
    print(f"run_id={run_id}")
