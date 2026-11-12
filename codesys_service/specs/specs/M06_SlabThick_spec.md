# M06_SlabThick · Slab Thickness Alarm and Fault History — Formal Specification (LTL)

## Conventions
Each LTL state is the end of one scan cycle; `CycleTime` is the interval represented by that cycle. `validFault := THICKNESS_SIGNAL_VALID AND THICKNESS_FAULT`; `holdAcc` is the time since the alarm was last triggered.



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
| P1 | Alarm trigger | A valid fault activates the alarm in the same cycle. | `G(validFault -> THICKNESS_ALARM)` |
| P2 | Minimum hold | A triggered alarm stays active for at least 500 ms. | `G((THICKNESS_ALARM AND holdAcc < 500ms AND X THICKNESS_SIGNAL_VALID) -> X THICKNESS_ALARM)` |
| P3 | Alarm hold | The alarm stays active while the fault persists. | `G((THICKNESS_ALARM AND X validFault) -> X THICKNESS_ALARM)` |
| P4 | Alarm release | After the fault clears and 500 ms have elapsed, the alarm is released. | `G((NOT THICKNESS_FAULT AND holdAcc >= 500ms) -> NOT THICKNESS_ALARM)` |
| P5 | Invalid signal | An invalid signal switches the alarm off immediately and clears its holding state. | `G(NOT THICKNESS_SIGNAL_VALID -> NOT THICKNESS_ALARM)` |
| P6 | Counting | The counter increments exactly on each FALSE→TRUE transition of a valid fault. | `G((NOT validFault AND X validFault) -> X Slab_Fault_Counter = Slab_Fault_Counter + 1)` |
| P7 | Counting | The counter does not change otherwise. | `G(NOT (NOT validFault AND X validFault) -> X Slab_Fault_Counter = Slab_Fault_Counter)` |
| P8 | History | On a new fault the timestamp is stored at index 0 and older entries shift up. | `G((NOT validFault AND X validFault) -> X(Slab_Fault_History[0] = FaultTimestamp AND Slab_Fault_History[k] = old Slab_Fault_History[k-1] for k = 1..4))` |
| P9 | History | Only the five most recent entries are retained. | implied by P8 (entry 4 is discarded) |
| P10 | No recording | No fault is recorded while the signal is invalid. | `G(NOT THICKNESS_SIGNAL_VALID -> (X Slab_Fault_Counter = Slab_Fault_Counter AND X Slab_Fault_History[0] = Slab_Fault_History[0]))` |
| P11 | Runtime | Runtime accumulates only while cutting, with a valid signal and no fault. | `G((CUTTING_RUN AND THICKNESS_SIGNAL_VALID AND NOT THICKNESS_FAULT) -> X Slab_Runtime_Accumulator = Slab_Runtime_Accumulator + CycleTime)` |
| P12 | Runtime | Otherwise the accumulated value is preserved. | `G(NOT (CUTTING_RUN AND THICKNESS_SIGNAL_VALID AND NOT THICKNESS_FAULT) -> X Slab_Runtime_Accumulator = Slab_Runtime_Accumulator)` |
| P13 | Init | At power-up the alarm is off and all counters, runtime and history entries are zero. | `NOT THICKNESS_ALARM AND Slab_Fault_Counter = 0 AND Slab_Runtime_Accumulator = 0 AND FORALL k: Slab_Fault_History[k] = 0` (initial state) |
| P14 | Monotonic | The fault counter never decreases. | `G(X Slab_Fault_Counter >= Slab_Fault_Counter)` |

## Assumptions and requirement gaps
1. **Units**: `CycleTime` in ms; `Slab_Runtime_Accumulator` is compared in **milliseconds** (toolchain convention).
2. **Hold restart** ⚠️ Whether a fault recurring inside the 500 ms window restarts the hold is unspecified. The team adopted a **TOF** timer (the original window simply expires), so the tests drive it through `hold_ms`.
3. **Validity returning with a fault already TRUE** is treated as a new fault edge, because the previous state was cleared when the signal became invalid (TC05). ⚠️
4. **History is read-only to callers**; the specification does not constrain external writes.

## Test cases

File: `M06_SlabThick.testcase.json` (5 cases, 32 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | 500 ms minimum hold, boundary, release | P1, P2, P4, P13 |
| TC02 | Alarm held while the fault persists, no repeated counting | P3, P6, P7 |
| TC03 | Six faults: counting, index 0 newest, shifting, oldest dropped | P6, P8, P9, P14 |
| TC04 | Runtime only during normal cutting (stopped / fault / invalid) | P11, P12 |
| TC05 | Invalid signal clears the alarm and blocks recording | P5, P10 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **5/5 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **5/5 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 5 cases / 32 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
