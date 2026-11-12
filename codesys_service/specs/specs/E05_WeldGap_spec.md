# E05_WeldGap · Weld Gap Alarm and Startup Inhibition — Formal Specification (LTL)

## Conventions
Each LTL state is the end of one scan cycle. `initElapsed` is the time since power-up; `debAcc` the accumulated continuous TRUE time of `Gap_Exceeded` after initialisation.



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
| P1 | Safety | The emergency stop immediately clears the alarm and has priority over everything else. | `G(NOT Weld_E_Stop_NC -> NOT Operator_Alert)` |
| P2 | Inhibition | During the first 5 s after power-up the alarm is suppressed. | `G(initElapsed < 5s -> NOT Operator_Alert)` |
| P3 | Inhibition flag | `Weld_Soft_Start_Active` is TRUE exactly during the power-up inhibition period. | `G(Weld_Soft_Start_Active <-> (initElapsed < 5s AND Weld_E_Stop_NC))` |
| P4 | Inhibition | Debounce time does not accumulate during inhibition. | `G(initElapsed < 5s -> debAcc = 0)` |
| P5 | Debounce | The alarm is raised only after `Gap_Exceeded` has been continuously TRUE for `DebounceTime`. | `G(Operator_Alert -> debAcc >= DebounceTime)` |
| P6 | Debounce | A FALSE gap signal switches the alarm off and clears the timing. | `G(NOT Gap_Exceeded -> (NOT Operator_Alert AND X debAcc <= CycleTime))` |
| P7 | Liveness | After initialisation, with the e-stop inactive and the gap signal held for `DebounceTime`, the alarm is raised. | `G((Weld_E_Stop_NC AND initElapsed >= 5s AND Gap_Exceeded AND debAcc >= DebounceTime) -> Operator_Alert)` |
| P8 | Priority | The emergency stop also clears incomplete debounce timing. | `G(NOT Weld_E_Stop_NC -> X debAcc <= CycleTime)` |
| P9 | Init | At power-up the alarm is FALSE and the inhibition flag TRUE. | `NOT Operator_Alert AND Weld_Soft_Start_Active` (initial state) |
| P10 | Scope | `Weld_Soft_Start_Active` is FALSE after the inhibition period and never returns. | `G(initElapsed >= 5s -> NOT Weld_Soft_Start_Active)` |

## Assumptions and requirement gaps
1. **Inhibition timing during an emergency stop**: the requirement says the e-stop has priority over initialisation. We assume the 5 s inhibition timer does not advance while the e-stop is active, and `Weld_Soft_Start_Active` is FALSE then (P3). ⚠️
2. **Alarm release** is immediate when the gap clears ("switch off the alarm"), with no minimum hold.
3. **Inhibition is one-shot**: it applies only after power-up, not after an e-stop release (P10).

## Test cases

File: `E05_WeldGap.testcase.json` (3 cases, 18 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | 5 s inhibition, alarm suppressed, debounce starts only afterwards | P2, P3, P4, P9, P10 |
| TC02 | Debounce: short gap ignored, full debounce raises the alarm, FALSE clears it | P5, P6, P7 |
| TC03 | Emergency-stop priority, timing cleared, full debounce after release | P1, P8 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **3/3 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **3/3 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 3 cases / 18 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
