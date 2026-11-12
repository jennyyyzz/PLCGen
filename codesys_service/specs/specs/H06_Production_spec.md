# H06_Production · Production Control — Formal Specification (LTL)

## Conventions

- Each LTL state is the PLC state at the end of one scan cycle. `G` always, `X` next cycle, `->` implies.
- `Mode = FALSE` manual, `Mode = TRUE` automatic.



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

- `qualified := weight >= 100.0 AND weight <= 200.0`
- `stopped := NOT MotorForward AND NOT MotorReverse`
- `anySensor := SensorWash OR SensorWeight OR SensorFiring OR SensorOutput`

## Properties

### Common

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P1 | Interlock | Forward and reverse are never commanded together. | `G(NOT (MotorForward AND MotorReverse))` |
| P2 | Init | All Boolean outputs OFF and firingTemp = 0 at power-up. | `stopped AND NOT kick AND NOT CompletionLight AND firingTemp = 0.0` (initial state) |

### Manual mode

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P3 | Jog | Forward/reverse buttons jog the motor with interlock; no button → stop. | `G(NOT Mode -> ((MotorForward <-> (ForwardButton AND NOT ReverseButton)) AND (MotorReverse <-> (ReverseButton AND NOT ForwardButton))))` |
| P4 | No process outputs ⚠️ | kick and CompletionLight are OFF in manual mode. | `G(NOT Mode -> (NOT kick AND NOT CompletionLight))` |

### Automatic mode

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P5 | No reverse | The motor never reverses in automatic mode. | `G(Mode -> NOT MotorReverse)` |
| P6 | Start | Material at the feed station (line idle) starts forward motion. | `G((Mode AND stopped AND NOT CompletionLight AND NOT anySensor AND X(Mode AND SensorFeed)) -> X MotorForward)` |
| P7 | Stop on arrival | Reaching any station sensor while moving stops the motor. | `G((Mode AND MotorForward AND X(Mode AND anySensor)) -> X stopped)` |
| P8 | Latched motion | Between stations the motor keeps running. | `G((Mode AND MotorForward AND X(Mode AND NOT anySensor)) -> X MotorForward)` |
| P9 | Wash → weigh | At the wash station, washComplete restarts forward motion. | `G((Mode AND SensorWash AND stopped AND X(Mode AND SensorWash AND rise(washComplete))) -> X MotorForward)` |
| P10 | Wait at wash | Without washComplete the motor stays stopped at the wash station. | `G((Mode AND SensorWash AND stopped AND X(Mode AND SensorWash AND NOT washComplete)) -> X stopped)` |
| P11 | Qualified | At the weigh station, weightComplete with a qualified weight: no kick, motor forward, firingTemp = 500 + (weight − 100) × 0.5. | `G((Mode AND SensorWeight AND stopped AND X(Mode AND SensorWeight AND rise(weightComplete) AND qualified)) -> X(NOT kick AND MotorForward AND firingTemp = 500.0 + (weight - 100.0) * 0.5))` |
| P12 | Rejected | At the weigh station, weightComplete with an unqualified weight: kick is issued and the motor does not move forward. | `G((Mode AND SensorWeight AND stopped AND X(Mode AND SensorWeight AND rise(weightComplete) AND NOT qualified)) -> X(kick AND NOT MotorForward))` |
| P13 | Kick only at weigh | kick is never issued except in the cycle of a weightComplete at the weigh station with an unqualified weight. | `G(kick -> (Mode AND SensorWeight AND weightComplete AND NOT qualified))` |
| P14 | Temperature range | firingTemp is always within 500..550 once set, or 0 before any qualified weighing. | `G(firingTemp = 0.0 OR (firingTemp >= 500.0 AND firingTemp <= 550.0))` |
| P15 | Temperature hold | firingTemp changes only at a qualified weighing. | `G((Mode AND NOT (SensorWeight AND X rise(weightComplete))) -> (firingTemp = X firingTemp))` |
| P16 | Firing → output | At the firing station, firingComplete restarts forward motion. | `G((Mode AND SensorFiring AND stopped AND X(Mode AND SensorFiring AND firingComplete)) -> X MotorForward)` |
| P17 | Light ON | Arrival at the output station turns the completion light on. | `G((Mode AND MotorForward AND X(Mode AND SensorOutput)) -> X(CompletionLight AND stopped))` |
| P18 | Light hold | The light stays on while the product remains at the output station. | `G((Mode AND CompletionLight AND X(Mode AND SensorOutput)) -> X CompletionLight)` |
| P19 | Light OFF | When the product is removed the light goes off. | `G((Mode AND X(Mode AND NOT SensorOutput)) -> X NOT CompletionLight)` |
| P20 | Wrong-station signals | A complete signal at a station other than its own has no effect on the motor. | e.g. `G((Mode AND SensorWash AND stopped AND X(Mode AND SensorWash AND NOT washComplete AND (weightComplete OR firingComplete))) -> X stopped)` and analogously for the weigh and firing stations |
| P21 | Manual buttons ignored | Jog buttons have no effect in automatic mode. | `G((Mode AND stopped AND NOT SensorFeed AND X(Mode AND ForwardButton AND NOT SensorFeed AND NOT washComplete AND NOT weightComplete AND NOT firingComplete)) -> X stopped)` |

## Assumptions and requirement gaps

1. **P4**: the requirement does not mention kick/light in manual mode; we assume OFF.
2. **kick duration**: not specified. We treat kick as a one-cycle pulse issued in the cycle the weight is judged unqualified (P12/P13); the tests only check kick = 1 in that cycle and kick = 0 after the rejected material has left the weigh station. An implementation that holds kick while SensorWeight remains TRUE also satisfies the tests except step 5 of TC04 (material already removed). ⚠️
3. **After rejection**: the requirement does not say what happens next. We assume the rejected material is removed by the kicker and the line returns to idle, ready for the next material at the feed station (TC04 step 6).
4. **Sensor FALSE between stations**: assumed (sensors only see the material at the station).
5. **Mode switch during motion**: switching to manual stops automatic motion immediately; switching back starts automatic mode idle (TC06). Not constrained beyond that.
6. **Temperature formula** `500 + (weight − 100) × 0.5` follows from the linear map 100..200 → 500..550; at weight = 100 → 500.0, 150 → 525.0, 200 → 550.0. REAL outputs are compared exactly in the tests because these values are exactly representable.

**Transition timing.** The adopted implementation updates its internal step in the triggering
cycle and drives the output in the **following** cycle; the test cases assert the output one
cycle after the trigger.

## Test cases

File: `H06_Production.testcase.json` (6 cases, 95 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Manual jog, interlock, process outputs OFF | P1–P4 |
| TC02 | Full automatic cycle, weight 150 → 525, light ON/OFF, next material | P5–P11, P16–P19 |
| TC03 | Boundary weights 100 and 200 (qualified), 120 → 510 linear mapping | P11, P14 |
| TC04 | Weights 99.9 and 200.1 → kick, motor stays stopped, line ready after rejection | P12, P13 |
| TC05 | Complete signals at wrong stations ignored, manual buttons ignored in auto | P10, P20, P21 |
| TC06 | Mode switch during motion | P3, P6 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **6/6 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **6/6 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 6 cases / 95 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
