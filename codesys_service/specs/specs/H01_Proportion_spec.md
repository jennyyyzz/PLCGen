# H01_Proportion · Material Proportioning Process Control — Formal Specification (LTL)

## Conventions

- Each LTL state is the PLC state at the end of one scan cycle. `G` always, `X` next cycle, `->` implies.
- `estop = FALSE` means emergency stop **triggered**; `opeMode = FALSE` manual, `TRUE` automatic.



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

- `allOff := NOT valveARun AND NOT valveBRun AND NOT valveCRun AND NOT valveDRun AND NOT mixMotorRun`
- `auto := estop AND opeMode`, `manual := estop AND NOT opeMode`
- `rise(b) := NOT b AND X b` (rising edge of button b between two consecutive cycles)
- `fillOutputs := valveARun OR valveBRun OR valveCRun` (a material valve is open)

## Properties

### Emergency stop and initialisation

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P1 | Safety | Whenever the emergency stop is triggered, every device is OFF in the same cycle. | `G(NOT estop -> allOff)` |
| P2 | Init | All devices are OFF at power-up. | `allOff` (initial state) |
| P3 | No auto-resume | After an emergency stop is released, nothing restarts by itself; in automatic mode a new autoStart is required. | `G((NOT estop AND X(auto AND NOT autoStart)) -> X allOff)` |

### Manual mode (`manual`)

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P4 | Toggle ON | A rising edge of valveAStart while valve A is OFF turns it ON (same for B, C, D, mixer). | `G((manual AND NOT valveARun AND rise(valveAStart) AND X manual) -> X valveARun)` |
| P5 | Toggle OFF | A rising edge of valveAStart while valve A is ON turns it OFF (same for B, C, D, mixer). | `G((manual AND valveARun AND rise(valveAStart) AND X manual) -> X NOT valveARun)` |
| P6 | Hold | Without a rising edge the state of valve A is unchanged (holding the button does not re-toggle). | `G((manual AND X(manual AND NOT rise_now(valveAStart))) -> (valveARun <-> X valveARun))` where `rise_now` is the edge evaluated in the next cycle |
| P7 | Independence | Only the device whose button has a rising edge changes state. | follows from P4–P6 applied per device |
| P8 | Auto inputs ignored | autoStart, levelSensor and mixMotorComplete have no effect in manual mode. | implied by P6 (the only way to change an output in manual mode is a button edge) |

### Automatic mode (`auto`)

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P9 | Start | When the process is idle, autoStart opens valve A. | `G((auto AND allOff AND X(auto AND rise(autoStart))) -> X valveARun)` |
| P10 | Idle | When idle and autoStart is not pressed, nothing starts. | `G((auto AND allOff AND X(auto AND NOT autoStart)) -> X allOff)` |
| P11 | A → B | Valve A closes and valve B opens when the level reaches 50 cm. | `G((auto AND valveARun AND X(auto AND levelSensor >= 50)) -> X(NOT valveARun AND valveBRun))` |
| P12 | A hold | Valve A stays open below 50 cm. | `G((auto AND valveARun AND X(auto AND levelSensor < 50)) -> X valveARun)` |
| P13 | B → mixer (two materials) | With processMode FALSE, valve B closes and the mixer starts at 80 cm; valve C is not opened. | `G((auto AND valveBRun AND X(auto AND levelSensor >= 80 AND NOT processMode)) -> X(NOT valveBRun AND mixMotorRun AND NOT valveCRun))` |
| P14 | B → C (three materials) | With processMode TRUE, valve B closes and valve C opens at 80 cm; the mixer does not start yet. | `G((auto AND valveBRun AND X(auto AND levelSensor >= 80 AND processMode)) -> X(NOT valveBRun AND valveCRun AND NOT mixMotorRun))` |
| P15 | B hold | Valve B stays open below 80 cm. | `G((auto AND valveBRun AND X(auto AND levelSensor < 80)) -> X valveBRun)` |
| P16 | C → mixer | Valve C closes and the mixer starts at 100 cm. | `G((auto AND valveCRun AND X(auto AND levelSensor >= 100)) -> X(NOT valveCRun AND mixMotorRun))` |
| P17 | C hold | Valve C stays open below 100 cm. | `G((auto AND valveCRun AND X(auto AND levelSensor < 100)) -> X valveCRun)` |
| P18 | Mixer → D | When mixing is complete the mixer stops and valve D opens; the process ends. | `G((auto AND mixMotorRun AND X(auto AND rise(mixMotorComplete))) -> X(NOT mixMotorRun AND valveDRun))` |
| P19 | Mixer hold | The mixer keeps running until mixMotorComplete. | `G((auto AND mixMotorRun AND X(auto AND NOT mixMotorComplete)) -> X mixMotorRun)` |
| P20 | Sequencing | In automatic mode at most one material valve is open at a time, and the mixer never runs while a material valve is open. | `G(auto -> (NOT(valveARun AND valveBRun) AND NOT(valveARun AND valveCRun) AND NOT(valveBRun AND valveCRun) AND NOT(mixMotorRun AND fillOutputs)))` |
| P21 | Manual buttons ignored | In automatic mode the manual toggle buttons have no effect. | `G((auto AND X(auto AND NOT autoStart AND levelSensor < 50 AND NOT mixMotorComplete)) -> (valveDRun <-> X valveDRun))` (representative instance; analogous for each device/phase) |
| P22 | No restart | autoStart during a running sequence does not restart it. | `G((auto AND valveBRun AND X(auto AND rise(autoStart) AND levelSensor < 80)) -> X valveBRun)` |

## Assumptions and requirement gaps

1. **Level thresholds** are read as "reaches" = `>=` (50, 80, 100 cm).
2. **End of the automatic process**: after valve D opens the requirement says "the process ends". We leave valve D open and do not constrain when it closes; a new autoStart is not required to close it. ⚠️ Test cases therefore do not check anything after D opens except the single cycle in which it opens.
3. **Emergency stop release**: not specified whether the automatic sequence resumes. We assume it does **not** (P3), which is the safe interpretation; a new autoStart restarts from valve A.
4. **Mode switching**: when switching from automatic to manual, the automatic sequence is aborted; outputs are then under manual control. The reverse switch starts automatic mode idle. Not covered by test cases to avoid over-constraining.
5. **Manual toggle semantics** are explicitly rising-edge (requirement text), so holding a button for several cycles toggles once (P6).
6. **Mixer-complete signal while the mixer is not running** is ignored (follows from P9–P19).

## Test cases

File: `H01_Proportion.testcase.json` (6 cases, 44 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Manual toggle on rising edge, hold does not re-toggle, independence, auto inputs ignored | P2, P4–P8 |
| TC02 | Automatic, processMode FALSE: A → B → mixer → D, thresholds 49/50 and 80 | P9, P11–P13, P18–P20 |
| TC03 | Automatic, processMode TRUE: A → B → C → mixer → D, threshold 99/100 | P14, P16–P18, P20 |
| TC04 | Emergency stop during mixing, held, released, restart from A | P1, P3, P9 |
| TC05 | Emergency stop in manual mode, buttons ignored during estop, OFF after release | P1, P3 |
| TC06 | Manual buttons ignored in auto; autoStart during sequence does not restart | P10, P21, P22 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **6/6 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **6/6 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 6 cases / 44 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
