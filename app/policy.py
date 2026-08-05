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
