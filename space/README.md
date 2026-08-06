---
title: ARBITER
emoji: ⚖️
colorFrom: indigo
colorTo: gray
sdk: gradio
app_file: app.py
pinned: false
license: mit
short_description: Reproduce web bugs, then prove it to an independent judge
---

# ARBITER

**Automated Reproduction of Bugs with Independent Trial Evidence Review**

An LLM agent reads a bug report, drives a real browser to reproduce it, and then has to
convince a separate model that never sees its reasoning that the evidence actually shows the
reported symptom. A claim the judge cannot verify does not count.

This Space is a demo of the parts that need no API key and no browser, which happen to be the
parts worth showing:

- **Benchmark results.** All ten reports, including two negative controls whose reports describe
  symptoms that do not exist, with the per-trial judge reasoning and the screenshots each verdict
  was based on.
- **The frame-difference oracle, live.** Upload any screen recording and the real oracle runs on
  it, the same numpy and OpenCV code the pipeline uses. It separates a smooth transition from a
  stepped, janky one by measuring how concentrated the pixel change is, which is a defect class
  the DOM cannot reveal because the DOM is identical either way.
- **Judge isolation, checked in front of you.** Pick any recorded trial. The payload shown is
  generated on the spot by the project's own `build_payload`, and the panel beside it verifies
  that the actor's written conclusion appears nowhere inside it.
- **An audit of the judge.** Each run's evidence reviewed against a different bug's report, which
  it cannot support. A judge that confirms everything would be worthless, so this measures whether
  it discriminates.

Results on the published run: 8 of 8 seeded bugs reproduced, 0 false positives on the 2 controls,
30 trials, about 11 cents. The judge refused all 8 mismatched pairs in the audit.

The benchmark is seeded rather than scraped, which makes ground truth exact and the suite
hermetic, and also makes it easier than the open world. Full limitations are in the source repo,
stated plainly.

- Source: https://github.com/adwitiyashukla/ARBITER
- Full HTML report: https://adwitiyashukla.github.io/ARBITER/

MIT licensed.
