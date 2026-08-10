"""Fake "risky" tools for the demo loop — placeholders to prove the
approval-gating mechanism works, not real integrations."""


def send_email(to: str, body: str) -> str:
    return f"Email sent to {to}: {body[:60]}..."


def execute_action(action_type: str, amount: float) -> str:
    return f"Executed {action_type} for amount=${amount}"


TOOLS = {
    "send_email": send_email,
    "execute_action": execute_action,
}
