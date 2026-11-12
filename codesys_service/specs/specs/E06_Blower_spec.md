# E06_Blower · Aeration Blower Delayed Start — Formal Specification (LTL)

## Conventions
Each LTL state is the end of one scan cycle. `delayAcc` is the accumulated continuous time during which both start conditions held.



### Trigger semantics (applies to every property below)

Three kinds of input appear in these questions, and mixing them up is the most
common way to write a test case that cannot distinguish a correct implementation
from a broken one.

**1. Operator buttons and completion signals are edge-triggered.**
`*Button`, `*Start`, `*ConfirmButton`, `*Complete`. The requirement's wording
"the operator presses / triggers" cannot be satisfied by a level condition: a
button held down would fire the transition on every scan. Where such an input
drives a transition the formula uses

```
rise(b) := NOT b AND X b
```

read as "`b` goes FALSE → TRUE across the step into the next cycle".

**2. Sensors report presence and are level signals.**
`*Sensor`, `Gap_Exceeded`, `DO_LOW`, `VISCOSITY_OK`, … These stay TRUE for as long
as the condition holds, which may be many cycles, and appear **without** `rise`.

**3. Durations are not triggers.** `DebounceTime`, `Time`, `CycleTime` are
accumulated time, never edge-detected.

This convention is what the test cases in the companion `.testcase.json` assert:
each case releases a button before pressing it again, and TC cases that hold a
button across several cycles require the transition *not* to repeat.

## Properties

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P1 | Safety | The blower never runs during an emergency stop. | `G(NOT AERATION_E_STOP_NC -> NOT BLOWER_RUN)` |
| P2 | Safety | The blower never runs without a low-dissolved-oxygen demand. | `G(NOT DO_LOW -> NOT BLOWER_RUN)` |
| P3 | Delay | The blower runs only after both conditions have held continuously for 5 s. | `G(BLOWER_RUN -> delayAcc >= 5s)` |
| P4 | Reset | Loss of demand or an emergency stop resets the start timer. | `G((NOT DO_LOW OR NOT AERATION_E_STOP_NC) -> X delayAcc <= CycleTime)` |
| P5 | Liveness | While both conditions hold for 5 s the blower starts. | `G((DO_LOW AND AERATION_E_STOP_NC AND delayAcc >= 5s) -> BLOWER_RUN)` |
| P6 | Counting | The start counter increments exactly on each FALSE→TRUE transition of `BLOWER_RUN`. | `G((NOT BLOWER_RUN AND X BLOWER_RUN) -> X AERATION_BLOWER_CYCLE_COUNT = AERATION_BLOWER_CYCLE_COUNT + 1)` |
| P7 | Counting | The counter does not change without such a transition. | `G(NOT (NOT BLOWER_RUN AND X BLOWER_RUN) -> X AERATION_BLOWER_CYCLE_COUNT = AERATION_BLOWER_CYCLE_COUNT)` |
| P8 | Init | At power-up the blower is OFF and the count is zero. | `NOT BLOWER_RUN AND AERATION_BLOWER_CYCLE_COUNT = 0` (initial state) |
| P9 | Monotonic | The counter never decreases. | `G(X AERATION_BLOWER_CYCLE_COUNT >= AERATION_BLOWER_CYCLE_COUNT)` |

## Assumptions and requirement gaps
1. **Full delay after any interruption**: explicitly required ("a new demand must wait the full 5 seconds again").
2. **Counter overflow** of `UINT` is not specified and not tested.
3. **Emergency stop does not affect the counter** (only actual starts are counted).

## Test cases

File: `E06_Blower.testcase.json` (3 cases, 19 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | 5 s delay, run after the delay, no repeated counting while running | P3, P5, P6, P7, P8 |
| TC02 | Demand loss discards partial timing; full delay again; second start counted | P2, P4, P6 |
| TC03 | Emergency-stop priority, cannot start during e-stop, full delay after release | P1, P4, P9 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **3/3 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **3/3 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 3 cases / 19 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
