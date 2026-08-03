from arbiter import cost
from arbiter.models import (AGREED_NOT_REPRODUCED, CONFIRMED, DISPUTED, INCONCLUSIVE,
                            NOT_REPRODUCED, REJECTED, REPRODUCED, UNRESOLVED,
                            BugResult, BugSpec, TrialResult, Usage)
from arbiter.trial import combine


def spec(control=False, truth=REPRODUCED):
    return BugSpec(id="x", title="t", app="a.html", category="c",
                   ground_truth=truth, control=control, report="r")


def trial(actor, judge, outcome, i=0):
    return TrialResult(bug_id="x", trial_index=i, actor_verdict=actor, actor_reason="",
                       judge_verdict=judge, judge_confidence=0.9, judge_reason="",
                       judge_evidence=[], outcome=outcome, steps=[], signals=[],
                       actor_usage=Usage(), judge_usage=Usage(), duration_s=1.0,
                       evidence_dir="")


def test_combine_matrix():
    assert combine(REPRODUCED, REPRODUCED) == CONFIRMED
    assert combine(REPRODUCED, NOT_REPRODUCED) == REJECTED
    assert combine(NOT_REPRODUCED, REPRODUCED) == DISPUTED
    assert combine(NOT_REPRODUCED, NOT_REPRODUCED) == AGREED_NOT_REPRODUCED
    assert combine(REPRODUCED, INCONCLUSIVE) == UNRESOLVED


def test_only_confirmed_trials_count_as_reproductions():
    r = BugResult(spec=spec(), trials=[
        trial(REPRODUCED, REPRODUCED, CONFIRMED, 0),
        trial(REPRODUCED, NOT_REPRODUCED, REJECTED, 1),
    ])
    assert r.actor_claimed == 2
    assert r.confirmed == 1
    assert r.reproduction_rate == 0.5
    assert r.verdict == NOT_REPRODUCED, "a bare majority is required, 50 percent is not enough"


def test_stability_labels():
    conf = [trial(REPRODUCED, REPRODUCED, CONFIRMED, i) for i in range(10)]
    assert BugResult(spec=spec(), trials=conf).stability == "deterministic"
    mixed = conf[:4] + [trial(REPRODUCED, NOT_REPRODUCED, REJECTED, i) for i in range(6)]
    assert BugResult(spec=spec(), trials=mixed).stability == "flaky"
    none = [trial(NOT_REPRODUCED, NOT_REPRODUCED, AGREED_NOT_REPRODUCED, i) for i in range(4)]
    assert BugResult(spec=spec(), trials=none).stability == "never"


def test_control_reproduced_is_a_false_positive():
    r = BugResult(spec=spec(control=True, truth=NOT_REPRODUCED),
                  trials=[trial(REPRODUCED, REPRODUCED, CONFIRMED, i) for i in range(3)])
    assert r.verdict == REPRODUCED
    assert r.false_positive is True
    assert r.correct is False


def test_price_uses_longest_matching_prefix():
    assert cost.rate_for("gemini-3.5-flash-lite") == cost.PRICES["gemini-3.5-flash-lite"]
    assert cost.rate_for("gemini-3.6-flash-002") == cost.PRICES["gemini-3.6-flash"]
    assert cost.rate_for("something-unpriced") == cost.UNKNOWN_MODEL_PRICE


def test_price_math():
    u = Usage(prompt_tokens=1_000_000, completion_tokens=1_000_000, calls=1, model="gemini-3.6-flash")
    assert round(cost.price(u), 4) == round(1.50 + 7.50, 4)


def test_request_retry_backs_off_then_returns():
    import arbiter.llm.base as base

    class Resp:
        def __init__(self, code):
            self.status_code = code
            self.headers = {}

    calls = []

    def send():
        calls.append(1)
        return Resp(429 if len(calls) < 3 else 200)

    base.BASE_BACKOFF_S = 0.001
    out = base.request_with_retry(send, "test")
    assert out.status_code == 200
    assert len(calls) == 3, "should have retried twice before succeeding"


def test_request_retry_gives_up_and_returns_last_response():
    import arbiter.llm.base as base

    class Resp:
        status_code = 429
        headers = {}

    base.BASE_BACKOFF_S = 0.001
    out = base.request_with_retry(lambda: Resp(), "test")
    assert out.status_code == 429


def test_rate_limiter_spaces_calls():
    import time
    import arbiter.llm.base as base

    class Resp:
        status_code = 200
        headers = {}

    base.set_rate_limit(600)          # 100 ms apart
    base._last_call_at = 0.0
    start = time.monotonic()
    for _ in range(3):
        base.request_with_retry(lambda: Resp(), "test")
    elapsed = time.monotonic() - start
    base.set_rate_limit(0)
    assert elapsed >= 0.18, "three paced calls should take at least two intervals"


def test_circuit_breaker_trips_after_repeated_exhaustion():
    import arbiter.llm.base as base

    class Resp:
        status_code = 429
        headers = {}

    base.BASE_BACKOFF_S = 0.001
    base._consecutive_exhaustions = 0
    for _ in range(base.CONSECUTIVE_FAILURE_LIMIT - 1):
        base.request_with_retry(lambda: Resp(), "test")
    try:
        base.request_with_retry(lambda: Resp(), "test")
    except base.QuotaExhausted as exc:
        assert "quota" in str(exc).lower()
    else:
        raise AssertionError("expected QuotaExhausted after repeated exhaustion")
    base._consecutive_exhaustions = 0


def test_success_resets_the_circuit_breaker():
    import arbiter.llm.base as base

    class Ok:
        status_code = 200
        headers = {}

    base._consecutive_exhaustions = 2
    base.request_with_retry(lambda: Ok(), "test")
    assert base._consecutive_exhaustions == 0
