# E04_JamPump · Jam Pump Debouncing and Runtime Maintenance — Formal Specification (LTL)

## Conventions
Each LTL state is the end of one scan cycle; `CycleTime` is the time represented by that cycle. `debAcc` denotes the accumulated continuous valid time of `VISCOSITY_OK` (internal).



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
| P1 | Safety | An emergency stop immediately disables the run output. | `G(NOT PASTE_E_STOP_NC -> NOT VFD_RUN)` |
| P2 | Safety | The pump never runs while the viscosity signal is FALSE. | `G(NOT VISCOSITY_OK -> NOT VFD_RUN)` |
| P3 | Debounce | The pump runs only after the viscosity condition has been continuously valid for at least `DebounceTime`. | `G(VFD_RUN -> debAcc >= DebounceTime)` |
| P4 | Debounce | When the viscosity signal or the e-stop goes false, the accumulated debounce time is cleared. | `G((NOT VISCOSITY_OK OR NOT PASTE_E_STOP_NC) -> X(debAcc = 0 OR debAcc = CycleTime))` |
| P5 | Liveness | While both conditions hold continuously, the pump starts once `DebounceTime` has elapsed. | `G((VISCOSITY_OK AND PASTE_E_STOP_NC AND debAcc >= DebounceTime) -> VFD_RUN)` |
| P6 | Runtime | Runtime accumulates exactly by `CycleTime` while the pump runs. | `G(VFD_RUN -> X PUMP_RUNTIME_ACC = PUMP_RUNTIME_ACC + CycleTime)` |
| P7 | Runtime | Runtime is preserved while the pump is stopped. | `G(NOT VFD_RUN -> X PUMP_RUNTIME_ACC = PUMP_RUNTIME_ACC)` |
| P8 | Maintenance | The maintenance indication is set when the accumulated runtime reaches 500 hours. | `G(PUMP_RUNTIME_ACC >= 500h -> PUMP_MAINT_DUE)` |
| P9 | Maintenance | The indication is never set below 500 hours. | `G(PUMP_RUNTIME_ACC < 500h -> NOT PUMP_MAINT_DUE)` |
| P10 | Independence | The maintenance indication never affects the run output. | `G(PUMP_MAINT_DUE AND VISCOSITY_OK AND PASTE_E_STOP_NC AND debAcc >= DebounceTime -> VFD_RUN)` |
| P11 | Init | At power-up the run output is OFF, runtime zero and the indication FALSE. | `NOT VFD_RUN AND PUMP_RUNTIME_ACC = 0 AND NOT PUMP_MAINT_DUE` (initial state) |

## Assumptions and requirement gaps
1. **Units**: `TIME` inputs are in milliseconds. `PUMP_RUNTIME_ACC` is compared in **milliseconds**, matching `TIME_TO_LTIME` in the project toolchain (IEC nominally defines LTIME in nanoseconds).
2. **Debounce accumulation** ⚠️ The requirement supplies `CycleTime` as "the actual elapsed interval", which allows two readings: accumulate `CycleTime` per invocation (simulated time), or use a `TON` timer (wall-clock). The team adopted the **TON** reading, so the test cases drive the virtual scan clock through `hold_ms`.
3. **Maintenance flag latching**: the requirement does not mention a reset; we assume it stays TRUE once set. ⚠️
4. **500 hours** = 1 800 000 000 000 000 ns.

## Test cases

File: `E04_JamPump.testcase.json` (4 cases, 20 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Debounce accumulation, boundary at exactly `DebounceTime`, runtime starts | P3, P5, P6, P11 |
| TC02 | Viscosity loss stops the pump and clears timing; runtime preserved | P2, P4, P7 |
| TC03 | Emergency-stop priority, timing cleared, full debounce after release | P1, P4 |
| TC04 | 500 h maintenance threshold, flag does not affect operation | P8, P9, P10 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **4/4 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **4/4 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 4 cases / 20 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
