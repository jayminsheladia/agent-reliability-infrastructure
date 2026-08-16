from app.policy import PolicyRule, evaluate_policy


def test_unconditional_rule_requires_approval():
    rules = [PolicyRule(tool_name="send_email", condition=None, requires_approval=True)]
    assert evaluate_policy("send_email", {"to": "x", "body": "y"}, rules=rules) is True


def test_conditional_rule_requires_approval_when_condition_met():
    rules = [PolicyRule(tool_name="execute_action", condition="amount > 100", requires_approval=True)]
    assert evaluate_policy("execute_action", {"action_type": "x", "amount": 250}, rules=rules) is True


def test_conditional_rule_does_not_require_approval_when_condition_not_met():
    rules = [PolicyRule(tool_name="execute_action", condition="amount > 100", requires_approval=True)]
    assert evaluate_policy("execute_action", {"action_type": "x", "amount": 10}, rules=rules) is False


def test_unlisted_tool_defaults_to_no_approval_required():
    rules = [PolicyRule(tool_name="send_email", condition=None, requires_approval=True)]
    assert evaluate_policy("some_other_tool", {}, rules=rules) is False
