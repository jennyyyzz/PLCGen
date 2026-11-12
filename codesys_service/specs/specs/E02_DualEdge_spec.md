# E02_DualEdge · Dual-Word Edge Detection — Formal Specification (LTL)

## Conventions
Each LTL state is the end of one scan cycle. `prev` denotes `value` of the previous cycle (0 before the first invocation). `bit(x,i)` is bit *i* of `x`; `popcount(x)` the number of set bits.



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
| P1 | Rising mask | A bit of `risingBits` is set exactly when that bit went 0→1. | `G(X risingBits = (X value AND NOT value))` |
| P2 | Falling mask | A bit of `fallingBits` is set exactly when that bit went 1→0. | `G(X fallingBits = (value AND NOT X value))` |
| P3 | Change flag | `hasChanged` is TRUE exactly when the value differs from the previous cycle. | `G(X hasChanged <-> (X value <> value))` |
| P4 | Rising flag | `hasRisingEdges` is TRUE exactly when at least one rising edge occurred. | `G(hasRisingEdges <-> (risingBits <> 0))` |
| P5 | Falling flag | `hasFallingEdges` is TRUE exactly when at least one falling edge occurred. | `G(hasFallingEdges <-> (fallingBits <> 0))` |
| P6 | Rising count | `noOfRisingBits` equals the number of set bits in `risingBits`. | `G(noOfRisingBits = popcount(risingBits))` |
| P7 | Falling count | `noOfFallingBits` equals the number of set bits in `fallingBits`. | `G(noOfFallingBits = popcount(fallingBits))` |
| P8 | Disjointness | A bit cannot rise and fall in the same cycle. | `G((risingBits AND fallingBits) = 0)` |
| P9 | Consistency | `hasChanged` holds iff at least one edge of either direction occurred. | `G(hasChanged <-> (hasRisingEdges OR hasFallingEdges))` |
| P10 | No change | If the value is unchanged, all edge outputs are zero. | `G(NOT hasChanged -> (risingBits = 0 AND fallingBits = 0 AND noOfRisingBits = 0 AND noOfFallingBits = 0))` |
| P11 | Count bounds | Both counts are at most 32. | `G(noOfRisingBits <= 32 AND noOfFallingBits <= 32)` |
| P12 | First invocation ⚠️ | On the first cycle the previous value is treated as 0, so a non-zero input produces rising edges only. | `(value <> 0) -> (hasRisingEdges AND NOT hasFallingEdges)` (initial state) |

## Assumptions and requirement gaps
1. **P12**: the requirement does not define the state before the first invocation; we assume the stored previous value is 0 (standard IEC initialisation).
2. Outputs are computed every cycle; there is no enable input.

## Test cases

File: `E02_DualEdge.testcase.json` (4 cases, 18 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Single-bit rise/fall, unchanged cycles | P1–P5, P10, P12 |
| TC02 | Several simultaneous edges in both directions | P1, P2, P6–P9 |
| TC03 | Bit 31, all 32 bits at once (counts 31/32) | P6, P7, P11 |
| TC04 | Alternating patterns, disjoint masks | P8, P9 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **4/4 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **4/4 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 4 cases / 18 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
