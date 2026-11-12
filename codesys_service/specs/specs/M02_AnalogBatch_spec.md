# M02_AnalogBatch · Analog Batch Processing — Formal Specification (LTL)

## Conventions
Each LTL state is the end of one scan cycle. Channel *i* ranges over the first `count` elements. `ch[i]` abbreviates `channels[i]`.



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
| P1 | Scope | Only the first `count` channels are processed; the rest are untouched. | `G(i > count -> (X ch[i].outputValue = ch[i].outputValue AND X ch[i].retVal = ch[i].retVal))` |
| P2 | Enable | A disabled channel is not converted. | `G(NOT ch[i].enable -> X ch[i].outputValue = ch[i].outputValue)` |
| P3 | Mode error | An invalid `measuringMode` yields 16#8001 and no conversion. | `G((ch[i].enable AND ch[i].measuringMode NOT IN {0,1,2}) -> (ch[i].retVal = 16#8001 AND X ch[i].outputValue = ch[i].outputValue))` |
| P4 | Limit error | `hiLIM <= loLIM` yields 16#8002 and no conversion. | `G((ch[i].enable AND ch[i].hiLIM <= ch[i].loLIM) -> (ch[i].retVal = 16#8002 AND X ch[i].outputValue = ch[i].outputValue))` |
| P5 | Unipolar | Mode 0 with `bipolar = FALSE` maps 0..27648 linearly to loLIM..hiLIM. | `G(valid0(i) AND NOT ch[i].bipolar -> ch[i].outputValue = ch[i].loLIM + (analogValues[i] / 27648) * (ch[i].hiLIM - ch[i].loLIM))` |
| P6 | Bipolar | Mode 0 with `bipolar = TRUE` maps −27648..27648 linearly to loLIM..hiLIM. | `G(valid0(i) AND ch[i].bipolar -> ch[i].outputValue = ch[i].loLIM + ((analogValues[i] + 27648) / 55296) * (ch[i].hiLIM - ch[i].loLIM))` |
| P7 | Standard temp | Mode 1 gives one tenth of the raw value. | `G(valid1(i) -> ch[i].outputValue = analogValues[i] / 10.0)` |
| P8 | Climatic temp | Mode 2 gives one hundredth of the raw value. | `G(valid2(i) -> ch[i].outputValue = analogValues[i] / 100.0)` |
| P9 | Success status | A successfully converted channel reports 16#0000. | `G(converted(i) -> ch[i].retVal = 16#0000)` |
| P10 | Read-only input | `analogValues` is never modified. | `G(X analogValues[i] = analogValues[i])` |
| P11 | Read-only config | Configuration fields are never modified. | `G(X ch[i].enable = ch[i].enable AND X ch[i].hiLIM = ch[i].hiLIM AND X ch[i].loLIM = ch[i].loLIM AND X ch[i].bipolar = ch[i].bipolar AND X ch[i].measuringMode = ch[i].measuringMode)` |
| P12 | Independence | An error on one channel does not prevent other channels from being converted. | `G((ch[i].retVal = 16#8001 OR ch[i].retVal = 16#8002) AND valid0(j) -> converted(j))` |

`valid0(i)` = enabled, mode 0, `hiLIM > loLIM`; analogously for modes 1 and 2 (the limit check applies to every mode).

## Assumptions and requirement gaps
1. **Limit check scope**: the requirement states the `hiLIM <= loLIM` error without restricting it to mode 0; we apply it to every enabled channel. ⚠️
2. **Error priority**: an invalid mode (16#8001) is checked before the limits (16#8002); the requirement lists them in that order.
3. **`retVal` of disabled channels** is not specified and is not tested.
4. **Out-of-range raw values** (beyond ±27648) are not specified; linear extrapolation is assumed and not tested.

## Test cases

File: `M02_AnalogBatch.testcase.json` (3 cases, 11 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Unipolar and bipolar scaling at 0, mid and full scale | P5, P6, P9 |
| TC02 | Modes 1 and 2 including negative values | P7, P8 |
| TC03 | Invalid mode, `hiLIM <= loLIM`, disabled channel, `count` limit | P1–P4, P12 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **3/3 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **3/3 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 3 cases / 11 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
