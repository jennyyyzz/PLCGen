# M05_ProdLine · Automated Production Line Control — Formal Specification (LTL)

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

## Properties

### Common safety

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P1 | Interlock | Forward and reverse are never commanded together. | `G(NOT (MotorForward AND MotorReverse))` |
| P2 | Init | All outputs are OFF at power-up. | `NOT MotorForward AND NOT MotorReverse AND NOT CompletionLight` (initial state) |

### Manual mode (`NOT Mode`)

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P3 | Jog forward | Forward button alone drives the motor forward. | `G((NOT Mode AND ForwardButton AND NOT ReverseButton) -> MotorForward)` |
| P4 | Jog reverse | Reverse button alone drives the motor in reverse. | `G((NOT Mode AND ReverseButton AND NOT ForwardButton) -> MotorReverse)` |
| P5 | Interlock | Both buttons pressed: neither direction runs. | `G((NOT Mode AND ForwardButton AND ReverseButton) -> (NOT MotorForward AND NOT MotorReverse))` |
| P6 | Stop on release | No button: motor stops (no latching in manual). | `G((NOT Mode AND NOT ForwardButton AND NOT ReverseButton) -> (NOT MotorForward AND NOT MotorReverse))` |
| P7 | Light | The completion light is not used in manual mode. ⚠️ | `G(NOT Mode -> NOT CompletionLight)` |

### Automatic mode (`Mode`)

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P8 | No reverse | The motor never reverses in automatic mode. | `G(Mode -> NOT MotorReverse)` |
| P9 | Start at A | Product at A and ButtonA pressed (while idle) start forward motion. | `G((Mode AND NOT MotorForward AND NOT CompletionLight AND X(Mode AND SensorA AND rise(ButtonA))) -> X MotorForward)` |
| P10 | Stop at B | Arrival at B stops the motor. | `G((Mode AND MotorForward AND X(Mode AND SensorB)) -> X NOT MotorForward)` |
| P11 | Continue from B | At B, ButtonB restarts forward motion. | `G((Mode AND SensorB AND NOT MotorForward AND X(Mode AND SensorB AND rise(ButtonB))) -> X MotorForward)` |
| P12 | Stop at C | Arrival at C stops the motor. | `G((Mode AND MotorForward AND X(Mode AND SensorC)) -> X NOT MotorForward)` |
| P13 | Light ON | At C, ButtonC turns the completion light on. | `G((Mode AND SensorC AND NOT MotorForward AND X(Mode AND SensorC AND rise(ButtonC))) -> X CompletionLight)` |
| P14 | Light OFF | When the product is removed from C the light goes off. | `G((Mode AND X(Mode AND NOT SensorC)) -> X NOT CompletionLight)` |
| P15 | Light hold | While the product stays at C the light stays on. | `G((Mode AND CompletionLight AND X(Mode AND SensorC)) -> X CompletionLight)` |
| P16 | Latched motion | Once moving, the motor keeps running until the next station sensor is reached. | `G((Mode AND MotorForward AND X(Mode AND NOT SensorB AND NOT SensorC)) -> X MotorForward)` |
| P17 | Manual buttons ignored | Jog buttons have no effect in automatic mode. | `G((Mode AND NOT MotorForward AND X(Mode AND ForwardButton AND NOT (SensorA AND ButtonA) AND NOT (SensorB AND ButtonB))) -> X NOT MotorForward)` |
| P18 | Light only via ButtonC | The light never turns on without a prior ButtonC at C. | `G((Mode AND NOT CompletionLight AND X(Mode AND NOT (SensorC AND ButtonC))) -> X NOT CompletionLight)` |

## Assumptions and requirement gaps

1. **P7**: the requirement does not say what happens to the light in manual mode; we assume it is OFF (manual mode is for maintenance jogging).
2. **Mode switch during motion**: not specified. We assume switching to manual immediately stops automatic motion (P6 applies), and switching back to automatic resets the sequence to "waiting at A".
3. **Out-of-sequence buttons** (e.g. ButtonB while at A) are assumed to be ignored; this is the only reading consistent with the station-by-station description.
4. **Stop at B/C**: the requirement implies the motor stops when the *next* station sensor is reached; P10/P12 formalise that.
5. **Sensor dropout during motion**: sensors are assumed to be FALSE between stations (TC02 cycles 3 and 7).

**Transition timing.** The adopted implementation updates its internal step in the triggering
cycle and drives the output in the **following** cycle; the test cases assert the output one
cycle after the trigger.

## Test cases

File: `M05_ProdLine.testcase.json` (6 cases, 64 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Manual jog: forward, reverse, interlock, stop on release, auto signals ignored | P1–P7 |
| TC02 | Full automatic cycle A→B→C, light ON/OFF, next product | P8–P16 |
| TC03 | Wrong buttons / manual buttons ignored in auto | P9, P11, P13, P17, P18 |
| TC04 | Mode switch during motion stops the motor; manual jog; back to auto | P6, P2 |
| TC05 | A station button held in advance does not release the carriage | P9, P11 (edge semantics for the station buttons) |
| TC06 | Station sensors held while the operator works at the station | P10, P12, P16, P17 (sensors held TRUE as levels) |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **6/6 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **6/6 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 6 cases / 64 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
