from pathlib import Path

import yaml
from pydantic import BaseModel

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "policies" / "example.yaml"


class PolicyRule(BaseModel):
    tool_name: str
    condition: str | None = None
    requires_approval: bool = False


def load_policies(path: Path = DEFAULT_POLICY_PATH) -> list[PolicyRule]:
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return [PolicyRule(**rule) for rule in raw.get("rules", [])]


def evaluate_policy(tool_name: str, arguments: dict, rules: list[PolicyRule] | None = None) -> bool:
    """Return True if a proposed tool call requires human approval.

    Rules are checked in order; the first rule whose tool_name matches and
    whose condition (if any) evaluates true against the arguments wins. A
    tool with no matching rule defaults to not requiring approval — the
    policy is an allowlist of restrictions, not a default-deny gate.
    Conditions are trusted operator config (this project's own YAML), not
    external input, so a restricted eval (no builtins) is an acceptable way
    to support simple comparisons without a hand-rolled expression parser.
    """
    if rules is None:
        rules = load_policies()

    for rule in rules:
        if rule.tool_name != tool_name:
            continue
        if rule.condition is None:
            return rule.requires_approval
        try:
            if eval(rule.condition, {"__builtins__": {}}, arguments):
                return rule.requires_approval
        except Exception:
            continue

    return False
