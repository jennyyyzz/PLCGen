# M03_MovingAvg · Calculate Moving Average — Formal Specification (LTL)

## Conventions
Each LTL state is the end of one scan cycle. `n` denotes the number of stored samples, `window` the last `min(n, windowSize)` samples.



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
| P1 | Window error | A window size below 1 or above 100 produces an error and 16#8200. | `G((windowSize < 1 OR windowSize > 100) -> (error AND status = 16#8200))` |
| P2 | Normal status | With a valid window size no error is reported. | `G((windowSize >= 1 AND windowSize <= 100 AND NOT error_other) -> (NOT error AND status = 16#0000))` |
| P3 | Cyclic read | With `cyclicExecution` TRUE a new value is read every cycle. | `G((cyclicExecution AND validWindow AND NOT reset) -> X n = min(n + 1, windowSize))` |
| P4 | Trigger read | With `cyclicExecution` FALSE a value is read exactly on each rising edge of `trigger`. | `G((NOT cyclicExecution AND NOT trigger AND X trigger AND validWindow AND NOT reset) -> X n = min(n + 1, windowSize))` |
| P5 | No read | Without a cyclic read or a trigger edge the stored data is unchanged. | `G((NOT cyclicExecution AND NOT (NOT trigger AND X trigger)) -> X average = average)` |
| P6 | Trigger ignored | `cyclicExecution` overrides `trigger`. | implied by P3 |
| P7 | Average | The output equals the arithmetic mean of the stored window. | `G((validWindow AND n > 0) -> average = sum(window) / n)` |
| P8 | Window reached | `windowSizeReached` is TRUE exactly when the window is full. | `G(windowSizeReached <-> (n >= windowSize))` |
| P9 | Reset | `reset` clears the calculation. | `G(reset -> (average = 0 AND NOT windowSizeReached))` |
| P10 | Replacement | Once full, each new value replaces the oldest one. | `G((windowSizeReached AND read) -> X n = windowSize)` |
| P11 | Init | At power-up the average is 0 and the window is not reached. | `average = 0 AND NOT windowSizeReached` (initial state) |

## Assumptions and requirement gaps
1. **Average before the window is full**: the requirement does not specify it; we assume the mean of the samples collected so far (P7), which is the usual behaviour. ⚠️
2. **Reset priority**: `reset` is evaluated before reading a new value; the window-size error is checked before `reset`.
3. **Status on window error** is 16#8200 and the average is set to 0.
4. **Comparison tolerance**: `average` is LREAL; tests use values whose means are exactly representable except TC01 step 3 (36.666…), which the runner compares with full double precision.

## Test cases

File: `M03_MovingAvg.testcase.json` (5 cases, 24 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Cyclic averaging, window 3, oldest value replaced | P3, P7, P8, P10 |
| TC02 | Trigger mode: one read per rising edge, held trigger ignored | P4, P5 |
| TC03 | `cyclicExecution` overrides the trigger | P3, P6 |
| TC04 | Reset clears the calculation and it restarts | P9, P11 |
| TC05 | Window sizes 0, 101, negative, boundaries 1 and 100 | P1, P2 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **5/5 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **5/5 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 5 cases / 24 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
