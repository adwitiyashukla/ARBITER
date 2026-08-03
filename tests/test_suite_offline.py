"""Runs the whole suite, including report generation, with a stub driver and replayed
model traffic. Proves the orchestration, scoring, false-positive detection and report
writing all work without a browser or an API key."""
import io
import json
import os
import tempfile

import numpy as np
from PIL import Image

from arbiter import trial as trial_mod
from arbiter.config import RunConfig
from arbiter.models import REPRODUCED
from arbiter.report import write_report
from arbiter.trial import metrics, run_suite

APPS = os.path.join(os.path.dirname(__file__), "..", "benchmark", "apps")
BUGS = os.path.join(os.path.dirname(__file__), "..", "benchmark", "bugs")


def png(shade=240):
    buf = io.BytesIO()
    Image.new("RGB", (240, 160), (shade, shade, shade)).save(buf, format="PNG")
    return buf.getvalue()


class StubDriver:
    """Reports a page with one button, and a crash after the first action."""

    def __init__(self, crash):
        self.crash = crash
        self.acted = 0

    def start(self):
        pass

    def stop(self):
        return ""

    def goto(self, url):
        self.url_value = url

    @property
    def url(self):
        return getattr(self, "url_value", "http://stub/")

    def snapshot(self):
        return ({"url": self.url, "title": "stub", "viewport": {"width": 400, "height": 300},
                 "scrollY": 0,
                 "elements": [{"ref": 0, "tag": "button", "role": "", "text": "Delete", "value": "",
                               "id": "", "testid": "delete-1", "type": "", "disabled": False,
                               "checked": None, "focused": False, "clickable": True,
                               "editable": False, "checkable": False, "scrollable": False,
                               "fixed": False, "path": "body>button",
                               "rect": {"x": 5, "y": 5, "w": 60, "h": 20}}]},
                png(240 if self.acted == 0 else 255))

    def act_with_burst(self, action, frames=12, interval_ms=80):
        self.acted += 1
        self.crash.on_page_error("TypeError: seeded failure")
        burst = [np.full((60, 160), 240, dtype=np.uint8)] * 3 + \
                [np.full((60, 160), 255, dtype=np.uint8)] * 3
        return "ok", burst, [i * 80.0 for i in range(6)]


def write_traces(root, scope, replies):
    d = os.path.join(root, scope)
    os.makedirs(d, exist_ok=True)
    for i, text in enumerate(replies):
        with open(os.path.join(d, "{0:03d}.json".format(i)), "w", encoding="utf-8") as fh:
            json.dump({"text": text, "model": "gemini-3.6-flash",
                       "usage": {"prompt_tokens": 900, "completion_tokens": 60}}, fh)


ACTOR_CLAIMS = ['```json\n{"action":"click","ref":0}\n```',
                '```json\n{"action":"finish","verdict":"REPRODUCED","reason":"symptom seen"}\n```']
JUDGE_YES = json.dumps({"verdict": "REPRODUCED", "confidence": 0.9, "symptom_observed": "crash",
                        "evidence": ["page_error"], "reasoning": "matches the report"})
JUDGE_NO = json.dumps({"verdict": "NOT_REPRODUCED", "confidence": 0.8,
                       "symptom_observed": "app behaved correctly",
                       "evidence": ["no symptom in the final screen"],
                       "reasoning": "the steps ran but nothing is wrong"})


def test_full_suite_scores_and_reports(tmp_path=None):
    with tempfile.TemporaryDirectory() as tmp:
        traces = os.path.join(tmp, "traces")
        # seeded bug: actor claims, judge agrees.  control: actor claims, judge refuses.
        for bug, judge_reply in (("todo-crash", JUDGE_YES), ("search-filter-ok", JUDGE_NO)):
            write_traces(traces, "{0}/t0/actor".format(bug), ACTOR_CLAIMS)
            write_traces(traces, "{0}/t0/judge".format(bug), [judge_reply])

        original = trial_mod.DRIVER_FACTORY
        trial_mod.DRIVER_FACTORY = lambda crash, spec, cfg, ed: StubDriver(crash)
        try:
            cfg = RunConfig(provider="mock", actor_model="gemini-3.6-flash",
                            judge_model="gemini-3.6-flash", trials=1,
                            bugs_dir=BUGS, apps_dir=APPS, trace_dir=traces,
                            evidence_dir=os.path.join(tmp, "evidence"),
                            out_dir=os.path.join(tmp, "docs"),
                            only="todo-crash,search-filter-ok")
            suite = run_suite(cfg)
        finally:
            trial_mod.DRIVER_FACTORY = original

        m = metrics(suite)
        assert m["seeded_bugs"] == 1 and m["controls"] == 1
        assert m["reproduced"] == 1, "the seeded bug should be confirmed"
        assert m["false_positives"] == 0, "the judge refused the control, so no false positive"
        assert m["actor_claimed"] == 2 and m["judge_confirmed"] == 1
        assert m["judge_rejected"] == 1
        assert m["accuracy"] == 1.0
        assert m["cost"]["calls"] == 6          # 2 actor calls + 1 judge call, twice over
        assert m["cost"]["usd"] > 0

        paths = write_report(suite, cfg.out_dir)
        for key in ("json", "html", "markdown"):
            assert os.path.exists(paths[key])
        with open(paths["json"], encoding="utf-8") as fh:
            data = json.load(fh)
        assert len(data["bugs"]) == 2
        assert data["metrics"]["accuracy"] == 1.0
        html = open(paths["html"], encoding="utf-8").read()
        assert "todo-crash" in html and "search-filter-ok" in html
        assert "actor claims vs judge confirms" in html

        # the README injector must render from that exact artifact
        import importlib.util
        spec_ = importlib.util.spec_from_file_location(
            "inject", os.path.join(os.path.dirname(__file__), "..", "tools", "inject_results.py"))
        inject = importlib.util.module_from_spec(spec_)
        spec_.loader.exec_module(inject)
        md = inject.render(data)
        assert "seeded bugs reproduced" in md and "`todo-crash`" in md
        assert "would have been counted as successes" in md


def test_control_false_positive_is_detected(tmp_path=None):
    with tempfile.TemporaryDirectory() as tmp:
        traces = os.path.join(tmp, "traces")
        write_traces(traces, "search-filter-ok/t0/actor", ACTOR_CLAIMS)
        write_traces(traces, "search-filter-ok/t0/judge", [JUDGE_YES])

        original = trial_mod.DRIVER_FACTORY
        trial_mod.DRIVER_FACTORY = lambda crash, spec, cfg, ed: StubDriver(crash)
        try:
            cfg = RunConfig(provider="mock", trials=1, bugs_dir=BUGS, apps_dir=APPS,
                            trace_dir=traces, evidence_dir=os.path.join(tmp, "evidence"),
                            out_dir=os.path.join(tmp, "docs"), only="search-filter-ok")
            suite = run_suite(cfg)
        finally:
            trial_mod.DRIVER_FACTORY = original

        m = metrics(suite)
        assert m["false_positives"] == 1, "a confirmed reproduction on a control is a false positive"
        assert m["accuracy"] == 0.0
        assert suite.results[0].verdict == REPRODUCED
        assert suite.results[0].correct is False
