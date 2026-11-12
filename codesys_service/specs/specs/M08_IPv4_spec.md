# M08_IPv4 · IPv4 Parsing with Format and Range Checks — Formal Specification (LTL)

## Conventions
The function block is combinational: the output depends only on the current input. `wellFormed(ipText)` means four non-empty digit-only segments separated by periods, each with value 0..255.



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
| P1 | Correct parse | A well-formed address produces the value in network byte order. | `G(wellFormed(ipText) -> ipValue = s1*2^24 + s2*2^16 + s3*2^8 + s4)` |
| P2 | Byte order | The first segment occupies the most significant 8 bits. | contained in P1 |
| P3 | Malformed | Any malformed input produces 0. | `G(NOT wellFormed(ipText) -> ipValue = 0)` |
| P4 | Segment count | Fewer or more than four segments produce 0. | `G(segmentCount(ipText) <> 4 -> ipValue = 0)` |
| P5 | Empty segment | An empty segment produces 0. | `G(hasEmptySegment(ipText) -> ipValue = 0)` |
| P6 | Non-digit | Any non-digit, non-period character produces 0. | `G(hasNonDigit(ipText) -> ipValue = 0)` |
| P7 | Range | A segment above 255 produces 0. | `G(EXISTS k: segment_k > 255 -> ipValue = 0)` |
| P8 | Zero address | The valid address 0.0.0.0 also produces 0. | `G(ipText = "0.0.0.0" -> ipValue = 0)` |
| P9 | Determinism | The output depends only on the current input (no internal state). | `G((ipText = X ipText) -> (ipValue = X ipValue))` |

## Assumptions and requirement gaps
1. **Leading zeros** ("010.001.000.009") are accepted as decimal, since the requirement only demands decimal digits and a value within 0..255. ⚠️
2. **Whitespace** is not a digit, so " 1.2.3.4" and "1.2.3.4 " are malformed.
3. **Segment length**: a segment of more than three digits always exceeds 255 and is therefore rejected by P7.
4. **P8 is intentionally ambiguous** in the requirement: a zero output cannot distinguish "valid 0.0.0.0" from "invalid"; this is explicitly allowed.

## Test cases

File: `M08_IPv4.testcase.json` (4 cases, 23 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Typical, single-digit, maximum and loopback addresses | P1, P2 |
| TC02 | 0.0.0.0, smallest non-zero address, leading zeros | P8 |
| TC03 | Segments 256, 999 in various positions; 255 still accepted | P7 |
| TC04 | 3 and 5 segments, empty segments, leading/trailing periods, non-digits, wrong separator, empty string, trailing space | P3–P6 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **4/4 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **4/4 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 4 cases / 23 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
