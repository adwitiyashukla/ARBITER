"""End to end through the real Actor, Judge and combination rule, with a stub driver
and replayed model traffic. No browser and no network, so this runs anywhere, including CI."""
import io
import json
import os

from PIL import Image

from arbiter.agent import Actor
from arbiter.judge import Judge
from arbiter.llm.mock import MockProvider
from arbiter.models import CONFIRMED, REJECTED, REPRODUCED, NOT_REPRODUCED, BugSpec
from arbiter.oracle import CrashOracle
from arbiter.trial import combine


def png(color=(240, 240, 240)):
    buf = io.BytesIO()
    Image.new("RGB", (200, 120), color).save(buf, format="PNG")
    return buf.getvalue()


class FakeDriver:
    """Two screens: a list with one item, then the same list with the item gone."""

    def __init__(self):
        self.calls = []
        self.screens = [
            {"url": "http://test/todo.html", "title": "Tasklite",
             "viewport": {"width": 400, "height": 300}, "scrollY": 0,
             "elements": [
                 {"ref": 0, "tag": "button", "role": "", "text": "Delete", "value": "",
                  "id": "", "testid": "delete-1", "type": "", "disabled": False, "checked": None,
                  "focused": False, "clickable": True, "editable": False, "checkable": False,
                  "scrollable": False, "fixed": False, "path": "body>ul>li>button",
                  "rect": {"x": 10, "y": 10, "w": 60, "h": 24}},
                 {"ref": 1, "tag": "p", "role": "", "text": "1 task(s). Next up: Buy milk",
                  "value": "", "id": "summary", "testid": "", "type": "", "disabled": False,
                  "checked": None, "focused": False, "clickable": False, "editable": False,
                  "checkable": False, "scrollable": False, "fixed": False,
                  "path": "body>main>p", "rect": {"x": 10, "y": 50, "w": 200, "h": 20}}]},
            {"url": "http://test/todo.html", "title": "Tasklite",
             "viewport": {"width": 400, "height": 300}, "scrollY": 0, "elements": []},
        ]
        self.index = 0

    @property
    def url(self):
        return "http://test/todo.html"

    def snapshot(self):
        screen = self.screens[min(self.index, len(self.screens) - 1)]
        return screen, png() if self.index == 0 else png((255, 255, 255))

    def act_with_burst(self, action, frames=6, interval_ms=10):
        self.calls.append(str(action))
        self.index += 1
        import numpy as np
        burst = [np.full((60, 160), 240, dtype=np.uint8) for _ in range(3)]
        burst += [np.full((60, 160), 255, dtype=np.uint8) for _ in range(3)]
        return "ok", burst, [i * 10.0 for i in range(6)]


def write_traces(root, scope, replies):
    d = os.path.join(root, scope)
    os.makedirs(d, exist_ok=True)
    for i, text in enumerate(replies):
        with open(os.path.join(d, "{0:03d}.json".format(i)), "w", encoding="utf-8") as fh:
            json.dump({"text": text, "model": "mock",
                       "usage": {"prompt_tokens": 100, "completion_tokens": 20}}, fh)


SPEC = BugSpec(id="todo-crash", title="App breaks when the last task is deleted",
               app="todo.html", category="crash", ground_truth=REPRODUCED, control=False,
               report="Deleting the final task breaks the page.", max_steps=5)


def _run(tmpdir, judge_reply):
    traces = os.path.join(tmpdir, "traces")
    write_traces(traces, "t/actor", [
        'Delete the only task.\n```json\n{"action":"click","ref":0}\n```',
        'The summary vanished and an error was recorded.\n```json\n'
        '{"action":"finish","verdict":"REPRODUCED","reason":"summary line disappeared"}\n```',
    ])
    write_traces(traces, "t/judge", [judge_reply])

    actor_llm = MockProvider(trace_dir=traces)
    actor_llm.start_scope("t/actor")
    judge_llm = MockProvider(trace_dir=traces)
    judge_llm.start_scope("t/judge")

    crash = CrashOracle()
    driver = FakeDriver()
    evidence = os.path.join(tmpdir, "evidence")
    actor = Actor(actor_llm, driver, SPEC, crash, evidence)
    crash.on_page_error("TypeError: Cannot read properties of undefined (reading 'text')")
    verdict, reason, steps, signals = actor.run()
    jv = Judge(judge_llm).review(SPEC.prompt_view(), steps, signals, "final", evidence)
    return verdict, reason, steps, signals, jv, driver


def test_confirmed_path(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        verdict, reason, steps, signals, jv, driver = _run(tmp, json.dumps({
            "verdict": "REPRODUCED", "confidence": 0.9,
            "symptom_observed": "the summary line disappeared and a TypeError was thrown",
            "evidence": ["page_error at step 1"], "reasoning": "matches the report"}))
        assert driver.calls == ["click(ref=0)"]
        assert verdict == REPRODUCED
        assert any(s.kind == "page_error" for s in signals), "crash oracle signal missing"
        assert combine(verdict, jv.verdict) == CONFIRMED
        assert os.path.exists(os.path.join(tmp, "evidence", "step00_screen.png"))


def test_judge_can_reject_an_actor_claim(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        verdict, _, _, _, jv, _ = _run(tmp, json.dumps({
            "verdict": "NOT_REPRODUCED", "confidence": 0.7,
            "symptom_observed": "no breakage visible",
            "evidence": ["final screen renders normally"],
            "reasoning": "the steps ran but the described symptom is not visible"}))
        assert verdict == REPRODUCED
        assert combine(verdict, jv.verdict) == REJECTED, "an unconfirmed claim must not count"


def test_missing_trace_is_a_clear_error():
    import tempfile
    from arbiter.llm.base import LLMError
    with tempfile.TemporaryDirectory() as tmp:
        p = MockProvider(trace_dir=os.path.join(tmp, "traces"))
        p.start_scope("nothing/here")
        try:
            p.complete("s", "u", [])
        except LLMError as exc:
            assert "no recorded reply" in str(exc)
        else:
            raise AssertionError("expected LLMError")
