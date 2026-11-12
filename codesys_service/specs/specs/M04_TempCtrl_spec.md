# M04_TempCtrl · Temperature Logic Control — Formal Specification (LTL)

## Conventions
Each LTL state is the end of one scan cycle. `heatAcc` is the accumulated continuous time with `HeaterOutput` TRUE; `protAcc` the accumulated time with `OverheatProtection` TRUE.



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
| P1 | Display | The displays mirror the inputs every cycle. | `G(CurrentTemperature = TemperatureSensorInput AND SetTempDisplay = SetTemperature)` |
| P2 | Status | `HeaterStatus` reflects the heater output. | `G(HeaterStatus <-> HeaterOutput)` |
| P3 | Sensor fault | A value below 0 or above 100 turns the heater off. | `G((TemperatureSensorInput < 0.0 OR TemperatureSensorInput > 100.0) -> NOT HeaterOutput)` |
| P4 | Heating | Below the setpoint, without a fault or protection, the heater is on. | `G((TemperatureSensorInput < SetTemperature AND NOT fault AND NOT OverheatProtection) -> HeaterOutput)` |
| P5 | Cooling | At or above the setpoint the heater is off. | `G(TemperatureSensorInput >= SetTemperature -> NOT HeaterOutput)` |
| P6 | Overheat trip | After 5 s of continuous heating, protection is activated. | `G(heatAcc >= 5s -> OverheatProtection)` |
| P7 | Protection action | While protection is active the heater is off. | `G(OverheatProtection -> NOT HeaterOutput)` |
| P8 | Protection hold | Protection is held for at least 3 s. | `G(OverheatProtection -> (protAcc >= 3s OR X OverheatProtection))` |
| P9 | Protection release | Protection is released once 3 s have elapsed. | `G(protAcc >= 3s -> NOT X OverheatProtection)` |
| P10 | No false trip | Protection is not activated before 5 s of continuous heating. | `G((heatAcc < 5s AND NOT OverheatProtection) -> NOT X OverheatProtection)` |
| P11 | Timer restart | Interrupting the heater restarts the 5 s measurement. | `G(NOT HeaterOutput -> X heatAcc <= CycleTime)` |
| P12 | Init | At power-up the heater and protection are off. | `NOT HeaterOutput AND NOT OverheatProtection` (initial state) |

## Assumptions and requirement gaps
1. **Equality with the setpoint**: "lower than" and "higher than" leave `=` undefined; we treat `temperature = setpoint` as "do not heat" (P5). ⚠️
2. **Valid sensor range** is inclusive: 0 and 100 are valid values (the fault condition is `< 0` or `> 100`).
3. **Protection during a sensor fault**: the heater is off in both cases; no interaction is specified.
4. **After protection is released** normal control resumes immediately if the temperature is still below the setpoint.
5. The displays are updated even during a sensor fault (P1).

## Test cases

File: `M04_TempCtrl.testcase.json` (4 cases, 22 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Heating below/above/equal to the setpoint, displays | P1, P2, P4, P5 |
| TC02 | 5 s trip, 3 s hold, release and resume | P6, P7, P8, P9 |
| TC03 | Sensor fault below 0 and above 100, valid boundaries 0 and 100 | P3 |
| TC04 | Heating interrupted before 5 s does not trip protection | P10, P11 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **4/4 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **4/4 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 4 cases / 22 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
