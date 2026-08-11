import json


def extract_text(state: dict) -> str:
    """Pull plain text out of an event_log input_state/output_state JSONB
    value. Shared by embedding (Day 5) and trace display (Day 3) so both
    agree on what "the text of this state" means."""
    if not state:
        return ""
    if isinstance(state, dict) and isinstance(state.get("text"), str):
        return state["text"]
    return json.dumps(state, separators=(",", ":"))
