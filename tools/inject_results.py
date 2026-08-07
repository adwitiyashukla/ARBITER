from __future__ import annotations

import argparse
import json
import os
import sys

START = "<!-- RESULTS:START -->"
END = "<!-- RESULTS:END -->"
AUDIT_START = "<!-- AUDIT:START -->"
AUDIT_END = "<!-- AUDIT:END -->"


def render(data: dict) -> str:
    m = data["metrics"]
    cfg = data.get("config", {})
    seeded = [b for b in data["bugs"] if not b["control"]]
    controls = [b for b in data["bugs"] if b["control"]]

    trials_all = [t for b in data["bugs"] for t in b["trials"]]
    actor_models = sorted({t["actor_usage"]["model"] for t in trials_all if t["actor_usage"]["model"]})
    judge_models = sorted({t["judge_usage"]["model"] for t in trials_all if t["judge_usage"]["model"]})
    trial_seconds = sum(t.get("duration_s", 0.0) for t in trials_all)
    fmt = lambda ms: ", ".join("`{0}`".format(x) for x in ms) or "`unknown`"

    lines = [
        "Actor {0}, judge {1}, {2} trial(s) per report.".format(
            fmt(actor_models), fmt(judge_models), cfg.get("trials_per_bug", "?")),
        "",]
    if cfg.get("mode") == "rejudge":
        note = ("The verdicts here were produced on {0} in a second pass over the evidence the "
                "benchmark run had already saved. Nothing was re-run in the browser and no actor "
                "output was regenerated, so the judge saw exactly the screenshots, actions and "
                "signals from the original run.".format(data.get("started_at", "?")))
        if len(judge_models) > 1:
            note += (" Two judge models show up because the first one ran out of its daily free "
                     "quota partway through.")
        if set(judge_models) & set(actor_models):
            note += (" Actor and judge ended up on the same base model, which the free tier "
                     "forced. The judge still cannot see the actor's reasoning, and the audit "
                     "below is my attempt to check whether that is enough.")
        lines += [note, ""]
    lines += [
        "| metric | value |",
        "|---|---|",
        "| seeded bugs reproduced | **{0} / {1}** ({2:.0%}) |".format(
            m["reproduced"], m["seeded_bugs"], m["reproduction_rate"]),
        "| false positives on negative controls | **{0} / {1}** |".format(
            m["false_positives"], m["controls"]),
        "| overall accuracy against ground truth | **{0:.0%}** |".format(m["accuracy"]),
        "| trials run | {0} |".format(m["trials_total"]),
        "| trials where the actor claimed a reproduction | {0} |".format(m["actor_claimed"]),
        "| of those, confirmed by the independent judge | {0} |".format(m["judge_confirmed"]),
        "| rejected by the judge as unproven | {0} ({1:.0%} of claims) |".format(
            m["judge_rejected"], m["overclaim_rate"]),
        "| claimed but never confirmed | {0} ({1:.0%} of claims) |".format(
            m["actor_claimed"] - m["judge_confirmed"], m.get("unconfirmed_rate", 0.0)),
        "| judge overruled a negative actor verdict | {0} |".format(m["judge_disputed"]),
        "| inconclusive | {0} |".format(m["unresolved"]),
        "| reports reproducing in every trial | {0} |".format(m["deterministic"]),
        "| model calls | {0} |".format(m["cost"]["calls"]),
        "| tokens in / out | {0:,} / {1:,} |".format(
            m["cost"]["prompt_tokens"], m["cost"]["completion_tokens"]),
        "| cost at paid-tier rates | ${0:.4f} |".format(m["cost"]["usd"]),
        "| total trial time | {0:.0f}s across {1} trials |".format(trial_seconds, m["trials_total"]),
        "",
    ]

    rejected, unresolved = m["judge_rejected"], m["unresolved"]
    if rejected:
        lines += ["The actor claimed a reproduction {0} times and the judge threw out **{1}** of "
                  "them as not shown by the evidence. Those {1} would have counted as successes "
                  "in any setup where the agent grades its own work.".format(
                      m["actor_claimed"], rejected), ""]
    else:
        lines += ["The judge did not reject any of the {0} claims the actor made, so on this "
                  "benchmark the actor never overclaimed. That is a nice result and also a gap "
                  "in the evidence, which is what the audit below is for.".format(
                      m["actor_claimed"]), ""]
    if unresolved:
        lines += ["{0} trial(s) came out unresolved, meaning the judge said INCONCLUSIVE or "
                  "could not be reached. Those count as non-reproductions, never as "
                  "successes.".format(unresolved), ""]

    lines += ["### Per report", "",
              "| report | category | ground truth | verdict | reproduced in | stability | actor claimed / judge confirmed |",
              "|---|---|---|---|---|---|---|"]
    for b in data["bugs"]:
        trials = len(b["trials"])
        verdict = b["verdict"].lower().replace("_", " ")
        mark = "correct" if b["correct"] else "**wrong**"
        lines.append("| `{0}` | {1} | {2} | {3} ({4}) | {5}/{6} | {7} | {8} / {9} |".format(
            b["id"], b["category"],
            "bug" if not b["control"] else "control, no bug",
            verdict, mark,
            b["judge_confirmed"], trials, b["stability"],
            b["actor_claimed"], b["judge_confirmed"]))
    lines.append("")
    return "\n".join(lines)


def render_audit(a: dict) -> str:
    lines = [
        "A judge that agrees with everything is worth nothing, so this check hands it the "
        "evidence from one bug together with a **different** bug's report, which that evidence "
        "cannot possibly support. Judge model `{0}`.".format(a.get("judge_model", "?")),
        "",
        "**{0} of {1} mismatched pairs correctly refused.**".format(a["refused"], a["pairs"]),
        "",
        "| evidence from | judged against | verdict | outcome |",
        "|---|---|---|---|",
    ]
    for r in a["rows"]:
        lines.append("| `{0}` | `{1}` | {2} | {3} |".format(
            r["evidence_from"], r["judged_against"], r["verdict"],
            "correctly refused" if r["refused"] else "**rubber stamped**"))
    lines.append("")
    if a.get("rubber_stamped"):
        lines += ["{0} pair(s) got confirmed against evidence that cannot support them, which is "
                  "a real weakness in the judge prompt.".format(a["rubber_stamped"]), ""]
    return "\n".join(lines)


def replace_block(text: str, start: str, end: str, body: str) -> str:
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    return head + start + "\n" + body + end + tail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="docs/results.json")
    ap.add_argument("--readme", default="README.md")
    args = ap.parse_args()

    if not os.path.exists(args.results):
        print("no results at {0}. Run `python -m arbiter run` first.".format(args.results))
        return 1
    with open(args.results, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    with open(args.readme, "r", encoding="utf-8") as fh:
        readme = fh.read()
    if START not in readme or END not in readme:
        print("markers {0} / {1} not found in {2}".format(START, END, args.readme))
        return 1

    updated = replace_block(readme, START, END, render(data))

    audit_path = os.path.join(os.path.dirname(args.results) or ".", "judge_audit.json")
    if os.path.exists(audit_path) and AUDIT_START in updated:
        with open(audit_path, "r", encoding="utf-8") as fh:
            updated = replace_block(updated, AUDIT_START, AUDIT_END, render_audit(json.load(fh)))
        print("judge audit section updated from {0}".format(audit_path))

    with open(args.readme, "w", encoding="utf-8") as fh:
        fh.write(updated)
    print("README results section updated from {0}".format(args.results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
