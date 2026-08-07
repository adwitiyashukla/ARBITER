from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import types

FAILURES = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print("  {0} {1}{2}".format("[ok]  " if ok else "[FAIL]", label,
                                ("  <- " + detail) if detail else ""))
    if not ok:
        FAILURES.append(label)


def install_gradio_stub() -> None:

    class Any:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def __getattr__(self, name):
            return Any()

        def __call__(self, *a, **k):
            return Any()

    class StubModule(types.ModuleType):

        def __getattr__(self, name):
            return Any()

    sys.modules["gradio"] = StubModule("gradio")


def load_app(space_dir: str):
    space_dir = os.path.abspath(space_dir)
    app_path = os.path.join(space_dir, "app.py")
    if not os.path.exists(app_path):
        print("no app.py in {0}. Build the Space first with tools/build_space.py".format(space_dir))
        raise SystemExit(1)
    sys.path.insert(0, space_dir)
    spec = importlib.util.spec_from_file_location("space_app", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", required=True, help="a directory built by tools/build_space.py")
    args = ap.parse_args()

    install_gradio_stub()
    app = load_app(args.space)

    print("1. data loaded from the built Space")
    check(len(app.BUG_IDS) == 10, "ten reports present", str(len(app.BUG_IDS)))
    check(len(app.SPECS) == len(app.BUG_IDS), "a spec for every report")
    check(app.METRICS["seeded_bugs"] > 0, "metrics present")
    header = app.header_markdown()
    check("{0}/{1}".format(app.METRICS["reproduced"], app.METRICS["seeded_bugs"]) in header,
          "headline numbers come from results.json")
    hero = app.hero_html()
    check("{0}/{1}".format(app.AUDIT["refused"], app.AUDIT["pairs"]) in hero,
          "hero shows the adversarial audit result")
    check("arb-card" in hero and "<h1>ARBITER</h1>" in hero, "hero renders as styled HTML")

    print("\n2. results explorer, every report")
    for bug_id in app.BUG_IDS:
        md, gallery = app.show_bug(bug_id)
        ok = bug_id in md and "Trial 1" in md and len(md) > 400
        check(ok, "{0} renders".format(bug_id),
              "{0} chars, {1} screenshot(s)".format(len(md), len(gallery)))
        if not gallery:
            check(False, "{0} has evidence screenshots".format(bug_id), "gallery empty")

    print("\n3. frame-difference oracle, the three built-in examples")
    img, md = app.analyse_example("stepped")
    check(img is not None and "stepped_animation" in md, "a stepped animation is flagged as jank")
    check(img is not None and img.size[0] > 100, "chart rendered",
          "{0}".format(getattr(img, "size", None)))
    img, md = app.analyse_example("smooth")
    check("stepped_animation" not in md, "a smooth transition is NOT flagged as jank")
    check("smooth" in md.lower(), "smooth verdict reported")
    img, md = app.analyse_example("static")
    check("no_op" in md, "a screen that never changes is reported as a no-op")
    check(app.analyse([])[0] is None, "an unreadable clip fails gracefully")

    print("\n4. judge isolation, checked on every recorded trial")
    leaks = []
    for bug_id in app.BUG_IDS:
        trials = len(app.BUGS[bug_id]["trials"])
        for i in range(1, trials + 1):
            actor_md, payload, check_md = app.isolation_view(bug_id, str(i))
            reason = (app.BUGS[bug_id]["trials"][i - 1]["actor_reason"] or "").strip()
            if reason and reason in payload:
                leaks.append("{0} t{1}".format(bug_id, i))
    check(not leaks, "the actor's conclusion never appears in the judge payload",
          "checked {0} trials".format(sum(len(app.BUGS[b]["trials"]) for b in app.BUG_IDS)))
    actor_md, payload, check_md = app.isolation_view("todo-crash", "1")
    check("LEAKED" not in check_md, "live isolation check reports clean")
    check("BUG REPORT AS FILED" in payload, "payload is the real judge prompt")
    check("ARBITER-Judge" in payload, "judge system prompt included")

    print("\n5. judge audit tab")
    audit = app.audit_markdown()
    check("{0} of {1}".format(app.AUDIT["refused"], app.AUDIT["pairs"]) in audit,
          "audit totals rendered")
    check(all(r["evidence_from"] in audit for r in app.AUDIT["rows"]), "every audit row rendered")

    print("\n{0}".format("ALL SPACE CHECKS PASSED, safe to push"
                         if not FAILURES else "FAILURES: " + ", ".join(FAILURES)))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())
