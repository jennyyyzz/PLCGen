# E03_Hysteresis · Alarm Handling — Formal Specification (LTL)

## Conventions (shared by all questions)

- Each LTL state is the PLC state **at the end of one scan cycle**: the inputs read in that cycle together with the outputs computed in it.
- `G` = always (globally); `X` = in the next scan cycle; `F` = eventually; `->` = implies.
- Atomic propositions use the interface variable names directly. Status codes are written as `16#xxxx`.



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

## Abbreviations

- `valid := (loLevel < hiLevel) AND (hystWindow < hiLevel - loLevel)` — the parameters are valid.

## Properties

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P1 | Error handling | If loLevel ≥ hiLevel, error is TRUE and status is 16#8001. | `G((loLevel >= hiLevel) -> (error AND status = 16#8001))` |
| P2 | Error handling | If the limits are ordered but hystWindow ≥ hiLevel − loLevel, error is TRUE and status is 16#8002. | `G((loLevel < hiLevel AND hystWindow >= hiLevel - loLevel) -> (error AND status = 16#8002))` |
| P3 | Alarm trigger | With valid parameters, Value > hiLevel sets hiAlarm. | `G((valid AND Value > hiLevel) -> hiAlarm)` |
| P4 | Alarm release | With valid parameters, Value < hiLevel − hystWindow clears hiAlarm. | `G((valid AND Value < hiLevel - hystWindow) -> NOT hiAlarm)` |
| P5 | Alarm trigger | With valid parameters, Value < loLevel sets loAlarm. | `G((valid AND Value < loLevel) -> loAlarm)` |
| P6 | Alarm release | With valid parameters, Value > loLevel + hystWindow clears loAlarm. | `G((valid AND Value > loLevel + hystWindow) -> NOT loAlarm)` |
| P7 | Hysteresis (hold) | An active high alarm stays active while Value remains ≥ hiLevel − hystWindow. | `G((hiAlarm AND X(valid AND Value >= hiLevel - hystWindow)) -> X hiAlarm)` |
| P8 | Hysteresis (hold) | An active low alarm stays active while Value remains ≤ loLevel + hystWindow. | `G((loAlarm AND X(valid AND Value <= loLevel + hystWindow)) -> X loAlarm)` |
| P9 | No false alarm | An inactive high alarm is not set while Value ≤ hiLevel. | `G((NOT hiAlarm AND X(valid AND Value <= hiLevel)) -> X NOT hiAlarm)` |
| P10 | No false alarm | An inactive low alarm is not set while Value ≥ loLevel. | `G((NOT loAlarm AND X(valid AND Value >= loLevel)) -> X NOT loAlarm)` |
| P11 | Normal status ⚠️ | With valid parameters, no error is reported. | `G(valid -> (NOT error AND status = 16#0000))` |
| P12 | Mutual exclusion | With valid parameters the two alarms are never active together. | `G(valid -> NOT (hiAlarm AND loAlarm))` |

## Assumptions and requirement gaps

1. **P11 is an assumption.** The requirement does not specify `error`/`status` when the parameters are valid; we assume `error = FALSE` and `status = 16#0000` (common Siemens/CODESYS convention).
2. **Error priority.** When both error conditions hold, the requirement says the program exits on 16#8001, so 16#8001 takes priority (P2 is guarded by `loLevel < hiLevel`).
3. **Alarm outputs during an error** are not specified ("exit the program"), so no property constrains them.
4. **Boundary values.** Triggering uses strict comparisons (`>` / `<`), so `Value = hiLevel` does not trigger and `Value = hiLevel − hystWindow` does not release, exactly as worded.
5. **P12** follows from P3–P10 with valid parameters (hiLevel − hystWindow > loLevel), and is included as an explicit safety check.

## Test cases

File: `E03_Hysteresis.testcase.json` (5 cases, 23 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | High alarm: trigger, hold in window, boundary 75, release at 74, no trigger at exactly 80 | P3, P4, P7, P9 |
| TC02 | Low alarm: symmetric to TC01 | P5, P6, P8, P10 |
| TC03 | 16#8001 for loLevel > hiLevel and loLevel = hiLevel; priority over 16#8002 | P1 |
| TC04 | 16#8002 for hystWindow > range and = range; 59 is valid | P2, P11 |
| TC05 | Error clears after parameters are corrected; alarm logic works again | P1, P11, P3 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **5/5 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **5/5 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 5 cases / 23 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
