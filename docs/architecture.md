# ARBITER architecture

## Layers

```
benchmark/bugs/*.yaml     bug reports, ground truth, viewport, step budget
benchmark/apps/*.html     ten self-contained apps, one seeded defect each
        |
arbiter/server.py         local static server, so a run is hermetic and offline
        |
arbiter/driver/           the only browser-aware code. base.py is a five method contract
arbiter/perception.py     DOM -> element map + annotated screenshot + colour bands
arbiter/actions.py        the 15 action vocabulary, one source of truth for prompt,
                          driver and tests
        |
arbiter/agent.py          the actor loop
arbiter/oracle/           crash, visual, dom. facts only, never verdicts
        |
arbiter/judge.py          independent review from evidence alone
arbiter/trial.py          N trials, the combination rule, suite metrics
arbiter/cost.py           token and dollar accounting from provider usage data
arbiter/report.py         index.html, results.json, summary.md
```

## One step of the actor loop

1. `driver.snapshot()` evaluates `COLLECT_JS` in the page. It filters to visible elements that are
   interactive, editable, checkable, scrollable, pinned, or carry text, caps the list at 60, and
   stamps each one with `data-arbiter-ref="N"`. That attribute is how an action addresses an
   element later, which avoids asking the model to invent CSS selectors.
2. `perception.annotate()` draws numbered, colour-coded boxes on the screenshot.
3. `prompts.actor_user()` assembles the report, the recent action history, the signals raised
   since the last step, the element map and a coarse colour band summary.
4. The model replies with prose plus one fenced JSON action. `actions.parse()` extracts the JSON
   from anywhere in the reply, validates the name, the required arguments, rejects unknown
   arguments, coerces numeric fields and clamps `wait`. A malformed reply is fed back with the
   parser's own error message, twice, before the trial gives up.
5. `driver.act_with_burst()` captures a frame, executes the action, then samples 12 frames at
   roughly 80 ms with wall-clock stamps.
6. The three oracles turn that into `Signal` objects, which go into the next prompt and into the
   judge's evidence bundle.
7. A repeated-action guard warns the model when it emits the same action three times running.

## What the judge gets, and what it does not

Gets: the bug report as filed, the executed actions with their result strings, every signal with
its step index and severity, the final element map, and up to four raw (unannotated) screenshots
chosen by signal severity, each with a caption saying where in the run it came from.

Does not get: the actor's prose, its self-assessment, its `finish` action, or its verdict. This
is enforced by the signature of `judge.build_payload`, which has no parameter capable of carrying
them, and by `tests/test_judge_isolation.py`, which asserts both the signature and that a sentinel
string from the actor never appears in the rendered payload.

Raw screenshots rather than annotated ones is a deliberate choice: the overlay is an aid for the
actor, and showing the judge a pre-interpreted view of the screen would import the actor's
framing into what is supposed to be an independent look at the evidence.

## Scoring

- Trial outcome comes from `trial.combine(actor_verdict, judge_verdict)`.
- A trial counts as a reproduction only when the outcome is `CONFIRMED`.
- Bug-level verdict is `REPRODUCED` when a strict majority of trials are confirmed, so two of
  three is a reproduction and one of two is not.
- `stability` is `deterministic` at 0.9 and above, `flaky` from 0.3, `rare` below that, `never`
  at zero.
- A confirmed reproduction on a negative control is a false positive and makes the bug-level
  result incorrect.

## Determinism and replay

`--record` writes every model exchange to `traces/<bug>/t<n>/<actor|judge>/NNN.json` with a
fingerprint of the prompt. `--provider mock` replays them in call order and prints a warning if
the fingerprint has drifted, which happens when the prompt code changes but the trace has not
been re-recorded. CI runs the replay path, so the whole pipeline is exercised on a clean machine
with no secrets.

## Adding a platform

Implement `Driver`: `start`, `stop`, `goto`, `snapshot`, `act`, `act_with_burst`, plus a `url`
property. `snapshot` must return a dict with `url`, `title`, `viewport`, `scrollY` and a list of
elements carrying `ref`, `tag`, `text`, `value`, `id`, `testid`, `disabled`, `checked`,
`clickable`, `editable`, `checkable`, `scrollable`, `fixed`, `path` and a `rect`. Everything
above the driver, including all three oracles, then works unchanged.
