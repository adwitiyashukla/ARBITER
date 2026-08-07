# How the code is put together

Notes for anyone reading the source, including me in six months.

## Layout

```
benchmark/bugs/*.yaml     bug reports, ground truth, viewport, step budget
benchmark/apps/*.html     ten self-contained apps, one planted defect each
        |
arbiter/server.py         local static server so a run is offline and hermetic
        |
arbiter/driver/           the only browser-aware code, base.py is five methods
arbiter/perception.py     DOM to element map plus annotated screenshot
arbiter/actions.py        the 15 actions, one source of truth for prompt, driver and tests
        |
arbiter/agent.py          the actor loop
arbiter/oracle/           crash, visual, dom, facts only, no verdicts
        |
arbiter/judge.py          independent review from evidence
arbiter/trial.py          N trials, the combination rule, suite metrics
arbiter/cost.py           tokens and dollars from the provider's usage data
arbiter/report.py         index.html, results.json, summary.md
```

## One step of the actor loop

1. `driver.snapshot()` runs `COLLECT_JS` in the page. It keeps visible elements that are
   interactive, editable, checkable, scrollable, pinned or carry text, caps the list at 60, and
   stamps each one with `data-arbiter-ref="N"`. Actions address elements through that attribute,
   so the model never has to invent a CSS selector.
2. `perception.annotate()` draws numbered, colour-coded boxes on the screenshot.
3. `prompts.actor_user()` puts together the report, the recent action history, any signals raised
   since the last step, the element map, and a rough colour summary of the screen.
4. The model replies with a sentence or two and one fenced JSON action. `actions.parse()` digs
   the JSON out of wherever it ended up, validates the name and arguments, rejects anything
   unexpected, coerces the numeric fields and clamps `wait`. If the reply is unusable it goes
   back with the parser's own error attached, twice, then the trial gives up.
5. `driver.act_with_burst()` grabs a frame, runs the action, then samples 12 more at roughly
   80 ms with wall-clock timestamps.
6. The three oracles turn that into `Signal` objects, which go into the next prompt and into the
   evidence bundle for the judge.
7. If the model emits the same action three times running, the next prompt says so.

## What the judge gets

It gets the bug report, the executed actions with their result strings, every signal with its
step index and severity, the final element map, and up to four raw screenshots chosen by signal
severity, each with a caption saying where in the run it came from.

It does not get the actor's prose, its self-assessment, its `finish` action, or its verdict.
`judge.build_payload` has no parameter that could carry any of that, and
`tests/test_judge_isolation.py` checks both the signature and the rendered text.

The screenshots are the raw ones, not the annotated ones. The overlay is there to help the actor
address elements, and showing the judge a pre-interpreted view of the screen would drag the
actor's framing into what is supposed to be a fresh look.

## Scoring

- `trial.combine(actor_verdict, judge_verdict)` decides the outcome of a trial.
- Only `CONFIRMED` counts as a reproduction.
- A bug counts as reproduced when a strict majority of its trials are confirmed, so 2 of 3 is a
  reproduction and 1 of 2 is not.
- `stability` is `deterministic` at 0.9 and up, `flaky` from 0.3, `rare` below that, `never` at 0.
- A confirmed reproduction on a negative control is a false positive and makes that result wrong.

## Replay

`--record` writes every exchange to `traces/<bug>/t<n>/<actor|judge>/NNN.json` with a fingerprint
of the prompt. `--provider mock` plays them back in call order and warns if the fingerprint has
drifted, which happens when I change a prompt without re-recording. CI runs the replay path, so
the pipeline gets exercised on a clean machine with no secrets.

## Adding another platform

Implement `Driver`: `start`, `stop`, `goto`, `snapshot`, `act`, `act_with_burst`, and a `url`
property. `snapshot` returns a dict with `url`, `title`, `viewport`, `scrollY` and a list of
elements carrying `ref`, `tag`, `text`, `value`, `id`, `testid`, `disabled`, `checked`,
`clickable`, `editable`, `checkable`, `scrollable`, `fixed`, `path` and a `rect`. Everything
above the driver, all three oracles included, then works unchanged. An adb and UIAutomator2
version is the obvious next one.
