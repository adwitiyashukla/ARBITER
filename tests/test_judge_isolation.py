import inspect
import os

from arbiter import judge as judge_mod
from arbiter.judge import build_payload, parse_verdict
from arbiter.models import INCONCLUSIVE, NOT_REPRODUCED, REPRODUCED, Action, Signal, StepRecord

SECRET = "ACTOR-SECRET-CONCLUSION-XYZZY"


def _steps():
    return [
        StepRecord(0, "http://x/app.html", Action("click", {"ref": 3}), "ok", 12,
                   [], [Signal("crash", "page_error", "TypeError: cannot read id", 0, "hard")]),
        StepRecord(1, "http://x/app.html", Action("finish", {"verdict": REPRODUCED,
                                                             "reason": SECRET}), "run ended", 12, [], []),
    ]


def test_build_payload_cannot_receive_the_actor_verdict():
    params = set(inspect.signature(build_payload).parameters)
    assert "actor_verdict" not in params
    assert "actor_reason" not in params
    assert params == {"report", "steps", "signals", "final_state", "evidence_dir"}


def test_actor_reasoning_never_reaches_the_judge(tmp_path=None):
    steps = _steps()
    signals = [s for st in steps for s in st.signals]
    system, user, images, notes = build_payload(
        "a bug report", steps, signals, "final element map", evidence_dir="/nonexistent")
    assert SECRET not in user, "the actor's own conclusion leaked into the judge prompt"
    assert SECRET not in system
    assert images == []


def test_judge_prompt_demands_skepticism_and_allows_negative_answers():
    system = judge_mod.prompts.JUDGE_SYSTEM
    lowered = system.lower()
    assert "you did not perform those actions" in lowered
    assert "not reproduction" in lowered or "is not reproduction" in lowered
    assert "inconclusive" in lowered


def test_verdict_parsing_handles_fenced_json_and_junk():
    good = parse_verdict('```json\n{"verdict":"REPRODUCED","confidence":0.8,'
                         '"symptom_observed":"crash","evidence":["step 1"],"reasoning":"seen"}\n```')
    assert good.verdict == REPRODUCED and good.confidence == 0.8 and good.evidence == ["step 1"]

    bad = parse_verdict("I think maybe it happened?")
    assert bad.verdict == INCONCLUSIVE and bad.error

    weird = parse_verdict('{"verdict":"probably","confidence":5}')
    assert weird.verdict == INCONCLUSIVE and weird.confidence == 1.0
