# H02_FlexProcess · Flexible Processing Control — Formal Specification (LTL)

## Conventions
Each LTL state is the end of one scan cycle. `cur` is the station the product is currently at, `target = processSequence[k]` the active sequence entry.



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
| P1 | Interlock | The conveyor never runs in both directions. | `G(NOT (conveyorLeft AND conveyorRight))` |
| P2 | Start | Motion starts only when raw material is at station 1 and the start button is pressed. | `G((NOT conveyorLeft AND NOT conveyorRight AND k = 0 AND X NOT (sensor1 AND station1Start)) -> X(NOT conveyorLeft AND NOT conveyorRight))` |
| P3 | Direction | The conveyor moves right when the target station number is greater than the current one. | `G((moving AND target > cur) -> conveyorRight)` |
| P4 | Direction | The conveyor moves left when the target station number is smaller than the current one. | `G((moving AND target < cur) -> conveyorLeft)` |
| P5 | Stop on arrival | The conveyor stops when the sensor of the target station detects the product. | `G((conveyorLeft OR conveyorRight) AND X sensor[target] -> X(NOT conveyorLeft AND NOT conveyorRight))` |
| P6 | Wait for completion | At a processing station the conveyor stays stopped until that station reports completion. | `G((at(target) AND NOT complete[target]) -> (NOT conveyorLeft AND NOT conveyorRight))` |
| P7 | Advance | On the completion signal of the current station the sequence advances to the next entry. | `G((at(target_k) AND complete[target_k]) -> X k = k + 1)` |
| P8 | Wrong signals | A completion signal from a station the product is not at has no effect. | `G((at(target) AND NOT complete[target]) -> X(NOT conveyorLeft AND NOT conveyorRight))` |
| P9 | Termination | After the final entry (station 5) is reached, the conveyor stops and the cycle ends. | `G(sensor5 AND k = processLength -> (NOT conveyorLeft AND NOT conveyorRight))` |
| P10 | Latched motion | While in transit the conveyor keeps running. | `G((conveyorRight AND X NOT sensor[target]) -> X conveyorRight)` and analogously for `conveyorLeft` |
| P11 | Sequence scope | Only entries 1..`processLength` are used. | the implementation never reads `processSequence[i]` for `i > processLength` |

## Assumptions and requirement gaps
1. **The caller guarantees a valid sequence**: entries 2..4 for processing, the final entry is station 5, `processLength` 1..8 (stated in the requirement).
2. **Repeated station numbers** (e.g. [2,2,5]) are not specified; if the target equals the current station the product is already there and the completion signal advances the sequence immediately. Not tested. ⚠️
3. **Station 1 has no completion signal**; the start button plays that role.
4. **Sensors are FALSE between stations** (standard assumption of the line description).
5. **The start button is read as a level signal**; an edge-triggered implementation satisfies the same tests.

## Test cases

File: `H02_FlexProcess.testcase.json` (3 cases, 21 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Route 1 → 3 → 5: start, stop on arrival, continue after completion, end at station 5 | P2, P3, P5, P6, P9, P10 |
| TC02 | Route 1 → 4 → 2 → 5 requiring a leftward move | P3, P4, P7 |
| TC03 | Start without material, completion signals from the wrong station | P1, P2, P8 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **3/3 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **3/3 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 3 cases / 21 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
