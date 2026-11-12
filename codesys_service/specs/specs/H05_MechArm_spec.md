# H05_MechArm · Mechanical Arm Control — Formal Specification (LTL)

## Conventions

- Each LTL state is the PLC state at the end of one scan cycle. `G` always, `X` next cycle, `F` eventually, `U` until, `->` implies.
- `EmergencyStop = FALSE` means the emergency stop is **active**. The caller keeps the four mode inputs mutually exclusive.



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

- `estop := NOT EmergencyStop`
- `allOff := NOT MoveDown AND NOT MoveUp AND NOT MoveLeft AND NOT MoveRight AND NOT ActivateGrip AND NOT ActivateRelease`
- `auto := EmergencyStop AND (SingleStepMode OR SingleCycleMode OR ContinuousMode)`
- `home := UpLimitSwitch AND LeftLimitSwitch`
- `rise(Start) := NOT Start AND X Start`
- Cycle sequence: `down → grip → up → right → down → release → up → left`

## Properties

### Safety (all modes)

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P1 | Emergency stop | While the emergency stop is active every output is OFF. | `G(estop -> allOff)` |
| P2 | Limit switches | No motion/actuation is commanded into a position that is already reached. | `G((DownLimitSwitch -> NOT MoveDown) AND (UpLimitSwitch -> NOT MoveUp) AND (LeftLimitSwitch -> NOT MoveLeft) AND (RightLimitSwitch -> NOT MoveRight) AND (GripLimitSwitch -> NOT ActivateGrip) AND (ReleaseLimitSwitch -> NOT ActivateRelease))` |
| P3 | Opposite outputs | Opposite commands are never active together. | `G(NOT(MoveDown AND MoveUp) AND NOT(MoveLeft AND MoveRight) AND NOT(ActivateGrip AND ActivateRelease))` |
| P4 | Init | All outputs are OFF at power-up. | `allOff` (initial state) |
| P5 | No resume after estop | After the emergency stop is released, automatic motion does not resume by itself. | `G((estop AND X(auto AND NOT Start)) -> X allOff)` |

### Manual mode

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P6 | Jog | Each output equals its button AND NOT its limit switch (shown for down; analogous for up/left/right/grip/release). | `G((EmergencyStop AND ManualMode) -> (MoveDown <-> (DownButton AND NOT DownLimitSwitch)))` |
| P7 | Start ignored | Start has no effect in manual mode. | implied by P6 (outputs depend only on buttons and switches) |

### Automatic modes (common)

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P8 | Wait for Start | When idle, nothing moves until Start is pressed. | `G((auto AND allOff AND X(auto AND NOT Start)) -> X allOff)` |
| P9 | First action | From home, Start begins the down movement. | `G((auto AND allOff AND home AND X(auto AND rise(Start))) -> X MoveDown)` |
| P10 | Manual buttons ignored | Jog buttons have no effect in automatic modes. | `G((auto AND allOff AND X(auto AND NOT Start AND (DownButton OR UpButton OR LeftButton OR RightButton OR GripButton OR ReleaseButton))) -> X allOff)` |
| P11 | Action completes at limit | A running action stops when its limit switch is reached (down shown). | `G((auto AND MoveDown AND X(auto AND DownLimitSwitch)) -> X NOT MoveDown)` |
| P12 | Action persists | A running action continues until its limit switch is reached (down shown). | `G((auto AND MoveDown AND X(auto AND NOT DownLimitSwitch)) -> X MoveDown)` |
| P13 | Order | Actions follow the fixed order: grip is only commanded after down was completed, up after grip, right after up, … (representative instance). | `G(ActivateGrip -> DownLimitSwitch)`, `G(MoveRight -> (UpLimitSwitch AND GripLimitSwitch))`, `G(ActivateRelease -> (DownLimitSwitch AND RightLimitSwitch))`, `G(MoveLeft -> (UpLimitSwitch AND ReleaseLimitSwitch))` |

### Single-step mode

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P14 | One action per Start | After an action completes, the arm stays stopped until the next Start. | `G((SingleStepMode AND EmergencyStop AND allOff AND X(SingleStepMode AND EmergencyStop AND NOT Start)) -> X allOff)` |
| P15 | Start advances | When stopped after step k, Start begins step k+1 (e.g. at the bottom-left gripped position, Start → MoveUp). | `G((SingleStepMode AND EmergencyStop AND allOff AND DownLimitSwitch AND GripLimitSwitch AND LeftLimitSwitch AND X(SingleStepMode AND Start)) -> X MoveUp)` (one instance per step) |
| P16 | Held Start | Holding Start does not start the following action (edge semantics). | `G((SingleStepMode AND Start AND X(SingleStepMode AND Start) AND X allOff_after_completion) -> X allOff)` |

### Single-cycle mode

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P17 | Chaining | When an action completes, the next action starts without a new Start (down→grip shown). | `G((SingleCycleMode AND EmergencyStop AND MoveDown AND X(SingleCycleMode AND DownLimitSwitch AND NOT GripLimitSwitch)) -> X F ActivateGrip)` (within the next cycle) |
| P18 | Stop at home | After the left movement completes (arm back at home) the arm stops and waits for Start. | `G((SingleCycleMode AND MoveLeft AND X(SingleCycleMode AND LeftLimitSwitch)) -> X allOff)` and P8 afterwards |

### Continuous mode

| ID | Category | Natural language | LTL |
|---|---|---|---|
| P19 | Repeat | After the left movement completes, the next cycle's down movement starts without Start. | `G((ContinuousMode AND MoveLeft AND X(ContinuousMode AND LeftLimitSwitch AND NOT DownLimitSwitch)) -> X F MoveDown)` (within the next cycle) |

## Assumptions and requirement gaps

1. **Start is edge-triggered** in single-step mode ("pressed again"); holding Start must not run several steps. In single-cycle/continuous modes Start only matters when idle.
2. **Transition timing**: when a limit switch is reached, the completed action is OFF in that cycle; the next action may start in the same cycle or in the following one. Test cases allow one cycle of slack (two consecutive steps with the same inputs). ⚠️
3. **Emergency stop release**: not specified whether the interrupted cycle resumes. We assume it does **not** (P5); the sequence restarts from the beginning with a new Start (the arm is assumed to be returned manually to home).
4. **Mode change while running**: not specified; not tested.
5. **Limit switches** are assumed to be exclusive per axis (up/down, left/right, grip/release) and TRUE only at the end positions.
6. **Initial position** is top-left with the gripper released, as stated.

## Test cases

File: `H05_MechArm.testcase.json` (7 cases, 135 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Manual: all six buttons, stop at limit, stop on release, Start ignored | P2, P3, P6, P7 |
| TC02 | Single-step: eight actions each started by Start, held Start does not advance | P8, P9, P11–P16 |
| TC03 | Single-cycle: one Start chains all eight actions, stops at home, new Start restarts | P9, P11–P13, P17, P18 |
| TC04 | Continuous: cycles repeat without Start | P19 |
| TC05 | Emergency stop in auto and manual; Start/buttons blocked; no resume | P1, P5 |
| TC06 | Auto modes wait for Start; manual buttons ignored | P8, P10 |
| TC07 | Single-step mode: one Start press performs exactly one action | P9, P16 (Start edge; **fails on the Part-2 reference — DEFECT-H05-01**) |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **7/7 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **6/7 cases** — **1 case(s) FAIL** (see `CROSSCHECK.md`) |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 7 cases / 135 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
