## Results

| metric | value |
|---|---|
| seeded bugs reproduced | 8 / 8 (100%) |
| false positives on controls | 0 / 2 |
| overall accuracy | 100% |
| trials run | 30 |
| actor claimed reproduction | 24 trials |
| judge confirmed | 24 trials |
| judge rejected the actor's claim | 0 trials (0% of claims) |
| judge overruled a negative actor | 0 trials |
| model calls | 102 |
| tokens in / out | 269,938 / 10,071 |
| cost at paid-tier rates | $0.1062 |
| wall clock | 250s |

### Per report

| report | category | ground truth | verdict | reproduction rate | stability |
|---|---|---|---|---|---|
| `contact-residue` | state-residue | seeded bug | reproduced | 3/3 | deterministic |
| `double-submit` | race-condition | seeded bug | reproduced | 3/3 | deterministic |
| `drawer-jank` | animation-jank | seeded bug | reproduced | 3/3 | deterministic |
| `export-disabled` | disabled-control | seeded bug | reproduced | 3/3 | deterministic |
| `header-overlap` | responsive-layout | seeded bug | reproduced | 3/3 | deterministic |
| `modal-close` | unresponsive-control | seeded bug | reproduced | 3/3 | deterministic |
| `search-filter-ok` | negative-control | control | not reproduced | 0/3 | never |
| `stepper-skip` | logic | seeded bug | reproduced | 3/3 | deterministic |
| `theme-persist-ok` | negative-control | control | not reproduced | 0/3 | never |
| `todo-crash` | crash | seeded bug | reproduced | 3/3 | deterministic |
