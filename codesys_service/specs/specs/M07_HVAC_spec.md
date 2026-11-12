# M07_HVAC · Office HVAC Multi-mode Energy-Saving Control — Formal Specification (LTL)

## Conventions
Each LTL state is the end of one scan cycle. `night := HVAC_MODE_SELECTOR = 3`; `delayAcc` is the accumulated continuous time during which the fan conditions held.



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
| P1 | Fan condition | The fan never runs when unoccupied. | `G(NOT OCCUPANCY_DETECTED -> NOT SUPPLY_FAN_RUN)` |
| P2 | Night mode | The fan never runs in Night mode. | `G(night -> NOT SUPPLY_FAN_RUN)` |
| P3 | Delay | The fan runs only after the conditions have held continuously for 30 s. | `G(SUPPLY_FAN_RUN -> delayAcc >= 30s)` |
| P4 | Reset | Loss of occupancy or selecting Night mode resets the timing. | `G((NOT OCCUPANCY_DETECTED OR night) -> X delayAcc <= CycleTime)` |
| P5 | Liveness | While the conditions hold for 30 s the fan starts. | `G((OCCUPANCY_DETECTED AND NOT night AND delayAcc >= 30s) -> SUPPLY_FAN_RUN)` |
| P6 | Auto occupied | Auto mode, occupied: 0 °C. | `G((HVAC_MODE_SELECTOR = 0 AND OCCUPANCY_DETECTED) -> TEMP_SETPOINT_ADJUST = 0)` |
| P7 | Auto unoccupied | Auto mode, unoccupied: +3 °C in energy-saving mode, otherwise +2 °C. | `G((HVAC_MODE_SELECTOR = 0 AND NOT OCCUPANCY_DETECTED) -> (TEMP_SETPOINT_ADJUST = 3 <-> ENERGY_SAVING_MODE) AND (TEMP_SETPOINT_ADJUST = 2 <-> NOT ENERGY_SAVING_MODE))` |
| P8 | Comfort | Comfort mode: 0 °C occupied, +1 °C unoccupied. | `G(HVAC_MODE_SELECTOR = 1 -> (TEMP_SETPOINT_ADJUST = 0 <-> OCCUPANCY_DETECTED) AND (TEMP_SETPOINT_ADJUST = 1 <-> NOT OCCUPANCY_DETECTED))` |
| P9 | Economy | Economy mode: 0 °C occupied, +4 °C unoccupied. | `G(HVAC_MODE_SELECTOR = 2 -> (TEMP_SETPOINT_ADJUST = 0 <-> OCCUPANCY_DETECTED) AND (TEMP_SETPOINT_ADJUST = 4 <-> NOT OCCUPANCY_DETECTED))` |
| P10 | Night adjustment | Night mode: +4 °C regardless of occupancy. | `G(night -> TEMP_SETPOINT_ADJUST = 4)` |
| P11 | Energy-saving scope | The energy-saving selection affects Auto mode only. | `G(HVAC_MODE_SELECTOR <> 0 -> (TEMP_SETPOINT_ADJUST independent of ENERGY_SAVING_MODE))`, i.e. P8–P10 do not mention it |
| P12 | Range | The adjustment always stays within ±4 °C. | `G(TEMP_SETPOINT_ADJUST >= -4 AND TEMP_SETPOINT_ADJUST <= 4)` |
| P13 | Init | At power-up the fan is OFF and the adjustment 0. | `NOT SUPPLY_FAN_RUN AND TEMP_SETPOINT_ADJUST = 0` (initial state) |

## Assumptions and requirement gaps
1. **The adjustment is not delayed**: only the fan has a 30 s delay, so `TEMP_SETPOINT_ADJUST` follows the current inputs immediately (TC01 step 1). ⚠️
2. **Invalid selector values** are excluded by the requirement ("callers supply a valid value") and are not tested.
3. **Initial outputs** are OFF/0 until the first calculation, as stated in requirement 6.

## Test cases

File: `M07_HVAC.testcase.json` (3 cases, 24 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | 30 s fan delay, occupancy loss resets timing, full delay again | P1, P3, P4, P5, P13 |
| TC02 | Night mode stops the fan and blocks starting | P2, P4, P10 |
| TC03 | All four modes × occupied/unoccupied × energy-saving | P6–P12 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **3/3 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **3/3 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 3 cases / 24 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
