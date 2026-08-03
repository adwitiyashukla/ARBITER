"""Rewrite the Results section of README.md from run artifacts.

The point is that no number in the README is typed by a human. Run this after
`arbiter run` and the README, the HTML report and results.json cannot disagree.

    python tools/inject_results.py [--results docs/results.json] [--readme README.md]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

START = "<!-- RESULTS:START -->"
END = "<!-- RESULTS:END -->"


def render(data: dict) -> str:
    m = data["metrics"]
    cfg = data.get("config", {})
    seeded = [b for b in data["bugs"] if not b["control"]]
    controls = [b for b in data["bugs"] if b["control"]]

    lines = [
        "Run on {0}, actor `{1}`, judge `{2}`, {3} trial(s) per report.".format(
            data.get("started_at", "?"), cfg.get("actor", "?"), cfg.get("judge", "?"),
            cfg.get("trials_per_bug", "?")),
        "",
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
        "| judge overruled a negative actor verdict | {0} |".format(m["judge_disputed"]),
        "| inconclusive | {0} |".format(m["unresolved"]),
        "| reports reproducing in every trial | {0} |".format(m["deterministic"]),
        "| model calls | {0} |".format(m["cost"]["calls"]),
        "| tokens in / out | {0:,} / {1:,} |".format(
            m["cost"]["prompt_tokens"], m["cost"]["completion_tokens"]),
        "| cost at paid-tier rates | ${0:.4f} |".format(m["cost"]["usd"]),
        "| wall clock | {0:.0f}s |".format(m["duration_s"]),
        "",
    ]

    gap = m["actor_claimed"] - m["judge_confirmed"]
    if gap > 0:
        lines += ["The actor claimed a reproduction {0} times and the judge confirmed {1} of them. "
                  "The other {2} would have been counted as successes by a system that lets the "
                  "acting agent grade itself.".format(m["actor_claimed"], m["judge_confirmed"], gap), ""]
    else:
        lines += ["On this run the judge confirmed every claim the actor made, so actor and judge "
                  "agreed on all {0} claimed reproductions.".format(m["actor_claimed"]), ""]

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

    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    updated = head + START + "\n" + render(data) + END + tail
    with open(args.readme, "w", encoding="utf-8") as fh:
        fh.write(updated)
    print("README results section updated from {0}".format(args.results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
