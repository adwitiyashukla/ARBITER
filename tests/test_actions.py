import pytest

from arbiter import actions
from arbiter.actions import ActionError


def test_parses_action_from_fenced_block():
    text = 'I will open the dialog.\n```json\n[{"action": "click", "ref": 4}]\n```'
    parsed = actions.parse(text)
    assert len(parsed) == 1 and parsed[0].name == "click" and parsed[0].args["ref"] == 4


def test_parses_bare_object():
    assert actions.parse('{"action": "reload"}')[0].name == "reload"


def test_string_refs_are_coerced_to_int():
    assert actions.parse('{"action": "click", "ref": "7"}')[0].args["ref"] == 7


def test_unknown_action_is_rejected():
    with pytest.raises(ActionError):
        actions.parse('{"action": "teleport", "ref": 1}')


def test_missing_required_argument_is_rejected():
    with pytest.raises(ActionError):
        actions.parse('{"action": "type", "ref": 2}')


def test_unexpected_argument_is_rejected():
    with pytest.raises(ActionError):
        actions.parse('{"action": "click", "ref": 2, "force": true}')


def test_finish_verdict_must_be_valid():
    with pytest.raises(ActionError):
        actions.parse('{"action": "finish", "verdict": "MAYBE", "reason": "unsure"}')
    ok = actions.parse('{"action": "finish", "verdict": "NOT_REPRODUCED", "reason": "works fine"}')
    assert ok[0].args["verdict"] == "NOT_REPRODUCED"


def test_wait_is_clamped():
    assert actions.parse('{"action": "wait", "ms": 99999}')[0].args["ms"] == actions.MAX_WAIT_MS


def test_no_json_raises():
    with pytest.raises(ActionError):
        actions.parse("I am not sure what to do next.")


def test_schema_documented_for_every_action():
    doc = actions.schema_for_prompt()
    for name in actions.SCHEMA:
        assert name in doc
