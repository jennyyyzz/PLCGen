# H04_FIFO · FIFO First-In-First-Out Queue — Formal Specification (LTL)

## Conventions
Each LTL state is the end of one scan cycle. `cap` is the buffer capacity (array length), `rise(b) := NOT b AND X b`.



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
| P1 | Enqueue | A rising edge of `enqueue` on a non-full queue appends `item` and increments the count. | `G((rise(enqueue) AND elementCount < cap AND NOT X reset) -> X elementCount = elementCount + 1)` |
| P2 | Dequeue | A rising edge of `dequeue` on a non-empty queue removes the front element, writes it to `item` and decrements the count. | `G((rise(dequeue) AND elementCount > 0 AND NOT X reset) -> (X elementCount = elementCount - 1 AND X item = frontValue))` |
| P3 | FIFO order | Values are removed in insertion order. | for any two enqueued values, the one enqueued first is dequeued first |
| P4 | Full | An enqueue into a full queue is rejected with 16#8002 and changes nothing. | `G((rise(enqueue) AND elementCount = cap) -> (X status = 16#8002 AND X elementCount = elementCount AND X item = item))` |
| P5 | Empty | A dequeue from an empty queue is rejected with 16#8001 and changes nothing. | `G((rise(dequeue) AND elementCount = 0) -> (X status = 16#8001 AND X elementCount = 0 AND X item = item))` |
| P6 | Reset | `reset` empties the queue and takes priority over both requests. | `G(reset -> (elementCount = 0 AND status = 16#0000))` |
| P7 | Edge semantics | A held request performs only one operation. | `G((enqueue AND X enqueue) -> X elementCount = elementCount)` |
| P8 | Count bounds | The element count stays within 0..cap. | `G(elementCount >= 0 AND elementCount <= cap)` |
| P9 | Status | The status is 16#0000 for idle cycles, resets and successful operations. | `G((NOT rejectedEnq AND NOT rejectedDeq) -> status = 16#0000)` |
| P10 | Init | The queue is empty on the first invocation. | `elementCount = 0` (initial state) |
| P11 | Idle | Without a request the queue is unchanged. | `G((NOT rise(enqueue) AND NOT rise(dequeue) AND NOT reset) -> X elementCount = elementCount)` |
| P12 | Wrap-around | FIFO order is preserved across the physical end of the buffer. | contained in P3 |

## Assumptions and requirement gaps
1. **The caller never requests enqueue and dequeue in the same invocation** (stated in the requirement).
2. **Reset priority** over both operations is explicit; buffer contents need not be cleared.
3. **`item` on a rejected operation** stays unchanged (P4, P5).
4. **Capacity in the tests is 8** (`ARRAY[0..7]`), matching the project's reference implementation; the task itself derives capacity from the caller-supplied buffer, which the harness cannot represent as `VARIANT`. ⚠️
5. **Status of an idle cycle** is 16#0000 (P9).

## Test cases

File: `H04_FIFO.testcase.json` (5 cases, 66 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Enqueue/dequeue on rising edges, held signal ignored, FIFO order | P1, P2, P3, P7, P10 |
| TC02 | Filling to capacity, 16#8002 on overflow, space freed by a dequeue | P4, P8 |
| TC03 | 16#8001 on an empty dequeue, `item` untouched | P5, P9 |
| TC04 | Reset empties the queue and has priority over enqueue | P6, P11 |
| TC05 | Circular wrap-around preserves FIFO order | P3, P12 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **5/5 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **5/5 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 5 cases / 66 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
