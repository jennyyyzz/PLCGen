# M01_PumpSwitch · Multi-Pump Switching Control System — Formal Specification (LTL)

## Conventions
Each LTL state is the end of one scan cycle. `running` denotes the latched started state (set by `start`, cleared by `stop`). `top3(i)` means pump *i* is among the three highest priorities.



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
| P1 | Stop | `stop` stops every pump in the same cycle. | `G(stop -> FORALL i: NOT pumpGroup[i].RunComd)` |
| P2 | Idle | Before any `start`, no pump runs. | `G(NOT running -> FORALL i: NOT pumpGroup[i].RunComd)` |
| P3 | Manual | In manual mode a started pump runs exactly if it is selected. | `G((running AND NOT mode) -> FORALL i: (pumpGroup[i].RunComd <-> pumpGroup[i].selection))` |
| P4 | Automatic | In automatic mode exactly three pumps run. | `G((running AND mode) -> count(pumpGroup[i].RunComd) = 3)` |
| P5 | Automatic | A running pump has a priority at least as high as every stopped pump. | `G((running AND mode AND pumpGroup[i].RunComd AND NOT pumpGroup[j].RunComd) -> pumpGroup[i].priority >= pumpGroup[j].priority)` |
| P6 | Automatic | The manual selection has no effect in automatic mode. | follows from P4/P5 (outputs depend only on priority) |
| P7 | Read-only | The function block never writes `priority` or `selection`. | `G(X pumpGroup[i].priority = pumpGroup[i].priority AND X pumpGroup[i].selection = pumpGroup[i].selection)` |
| P8 | Standby | Exactly two pumps are on standby in automatic mode. | equivalent to P4 for a five-pump group |

## Assumptions and requirement gaps
1. **Start/stop semantics** ⚠️ The requirement describes buttons without fixing latching. The team adopted a **level** reading: `RunComd := start AND …`, so pumps run only while `start` is held and `stop` clears everything.
2. **Priority ties**: not specified. Any three pumps with the highest priorities satisfy P4/P5; with all priorities equal, exactly three must run (TC03).
3. **Selection changes while running** take effect immediately in manual mode (TC01).
4. **Mode switching while running** re-evaluates the outputs according to the new mode (TC03).

## Test cases

File: `M01_PumpSwitch.testcase.json` (3 cases, 15 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Manual: selected pumps run, selection change followed, stop stops all | P1, P2, P3 |
| TC02 | Automatic: three highest priorities, selection ignored, priority change followed | P4, P5, P6 |
| TC03 | Mode switching; equal priorities still select exactly three | P3, P4, P8 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **3/3 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **3/3 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 3 cases / 15 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
