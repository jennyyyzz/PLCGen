# E01_Filling · Automated Filling Line Control — Formal Specification (LTL)

## Conventions

- Each LTL state is the PLC state at the end of one scan cycle (inputs read in that cycle + outputs computed in it).
- `G` always, `X` next cycle, `->` implies. Interface variable names are used directly.



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

- `anyActuator := Pump_Motor OR Filling_Valve OR Capping_Machine OR Packing_Machine OR Completion_Light`
- `idle := NOT anyActuator`
- `onlyPump := Pump_Motor AND NOT Filling_Valve AND NOT Capping_Machine AND NOT Packing_Machine AND NOT Completion_Light` (and analogously `onlyValve`, `onlyCapping`, `onlyPacking`, `onlyLight`)

## Properties

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P1 | Init | At power-up all outputs are OFF. | `idle` (holds in the initial state) |
| P2 | Mutual exclusion | At most one stage output is active at any time. | `G(idle OR onlyPump OR onlyValve OR onlyCapping OR onlyPacking OR onlyLight)` |
| P3 | Start | In idle, a bottle at the sensor starts the cleaning pump. | `G((idle AND X rise(bottleSensor)) -> X Pump_Motor)` |
| P4 | Transition | During cleaning, the cleaning confirm button stops the pump and opens the filling valve. | `G((Pump_Motor AND X rise(cleaningConfirmButton)) -> X(Filling_Valve AND NOT Pump_Motor))` |
| P5 | Transition | During filling, the filling confirm button closes the valve and starts capping. | `G((Filling_Valve AND X rise(fillingConfirmButton)) -> X(Capping_Machine AND NOT Filling_Valve))` |
| P6 | Transition | During capping, the capping confirm button stops capping and starts packing. | `G((Capping_Machine AND X rise(cappingConfirmButton)) -> X(Packing_Machine AND NOT Capping_Machine))` |
| P7 | Transition | During packing, the packing confirm button stops packing and lights the completion light. | `G((Packing_Machine AND X rise(packingConfirmButton)) -> X(Completion_Light AND NOT Packing_Machine))` |
| P8 | Reset | When the light is on, finishedButton turns it off and returns to idle. | `G((Completion_Light AND X rise(finishedButton)) -> X idle)` |
| P9 | Latching | The pump keeps running until the cleaning confirm button is pressed (even if the sensor is released). | `G((Pump_Motor AND X NOT cleaningConfirmButton) -> X Pump_Motor)` |
| P10 | Latching | The valve stays open until the filling confirm button is pressed. | `G((Filling_Valve AND X NOT fillingConfirmButton) -> X Filling_Valve)` |
| P11 | Latching | Capping stays active until the capping confirm button is pressed. | `G((Capping_Machine AND X NOT cappingConfirmButton) -> X Capping_Machine)` |
| P12 | Latching | Packing stays active until the packing confirm button is pressed. | `G((Packing_Machine AND X NOT packingConfirmButton) -> X Packing_Machine)` |
| P13 | Latching | The light stays on until finishedButton is pressed. | `G((Completion_Light AND X NOT finishedButton) -> X Completion_Light)` |
| P14 | No spurious start | In idle, nothing starts without a bottle. | `G((idle AND X NOT bottleSensor) -> X idle)` |
| P15 | Sequence integrity | Each stage can only be entered from its predecessor (e.g. the valve never opens unless the pump was running in the previous cycle). | `G(X Filling_Valve -> (Pump_Motor OR Filling_Valve))`, and analogously for Capping_Machine, Packing_Machine, Completion_Light |

## Assumptions and requirement gaps

1. **Level vs. edge.** ⚠️ The requirement only says the operator "triggers" the signal. The team adopted **rising-edge** semantics for the confirmation buttons; the test cases therefore release the button between operations.
2. **Out-of-sequence buttons** are not mentioned; we assume they are ignored (P9–P14), which is the only interpretation consistent with "each step triggered by its own signal".
3. **A new bottle while the light is on** is not specified; we assume the cycle cannot restart until finishedButton (P13), since the operator must pick up the finished bottle first.
4. "Continues to work" (pump) is formalised as latching (P9).

**Transition timing.** The adopted implementation updates its internal step in the triggering
cycle and drives the output in the **following** cycle; the test cases assert the output one
cycle after the trigger.

## Test cases

File: `E01_Filling.testcase.json` (6 cases, 57 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Full cycle: each transition, one actuator at a time, outputs latched after trigger released, reset | P1–P13 |
| TC02 | Second bottle after reset runs the cycle again | P8, P3 |
| TC03 | Out-of-sequence / repeated buttons are ignored; nothing starts in idle without a bottle | P9–P15 |
| TC04 | Light stays on until finishedButton; other buttons do not clear it | P13 |
| TC05 | A confirm button held in advance does not skip a step | P4, P15 (edge semantics: a held button has no rising edge) |
| TC06 | A bottle that stays under the sensor does not restart the line | P3, P9–P13, P14, P15 (sensor held TRUE as a level) |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **6/6 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **6/6 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 6 cases / 57 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
