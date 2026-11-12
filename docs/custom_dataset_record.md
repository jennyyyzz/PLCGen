# Custom Question Bank dataset record

This document records the source, adaptation, rationality and diversity of the 12 custom questions.

## Naming

- Public questions: `FB_Q01`-`FB_Q20` (provided public question bank).
- Custom questions: `FB_C01`-`FB_C12` (this dataset).
- `FB` = Function Block (IEC 61131-3 POU); `Q` = public question bank; `C` = custom.

## Source and adaptation

All 12 questions are original scenarios written for this project. No external question text was copied. Each scenario is a synthesis of common industrial PLC patterns and was manually reduced to a single function block with deterministic scan-cycle behaviour.

| ID | Title | Difficulty | Primary axis | Source type |
| --- | --- | --- | --- | --- |
| C01 | Product Reject and Filtering Station | easy | sorting_filtering | independent conception |
| C02 | Two-Hand Safety Press | easy | safety_logic | independent conception |
| C03 | Automatic Barrier Gate | easy | cyclic_timing | independent conception |
| C04 | Star-Delta Motor Starter | medium | cyclic_timing | independent conception |
| C05 | Car Wash Sequence | medium | cyclic_timing | independent conception |
| C06 | Elevator Door Control | medium | safety_logic | independent conception |
| C07 | Bottle Height Sorting | medium | sorting_filtering | independent conception |
| C08 | Greenhouse Irrigation Zones | medium | cyclic_timing | independent conception |
| C09 | Conveyor Zone Accumulation | hard | sorting_filtering | independent conception |
| C10 | Boiler Purge and Ignition Sequence | hard | safety_logic | independent conception |
| C11 | Palletizer Layer Counting | hard | sorting_filtering | independent conception |
| C12 | Safety Light Curtain Muting | hard | safety_logic | independent conception |

## Rationality of the questions

| ID | Why the scenario is realistic |
| --- | --- |
| C01 | A reject station is a common end-of-line filtering task: good and defective parts must be classified, counted and separated without stopping the conveyor until a batch is complete. |
| C02 | Two-hand control prevents an operator from reaching into a press while it closes; the anti-tiedown timer catches a blocked or defeated button. |
| C03 | Vehicle barriers combine a short open command, a hold-open condition and a delayed close; the safety beam must reopen the gate at any time. |
| C04 | Star-delta starting is a standard motor-control sequence that requires a timed transition, contactor interlocking and a latched overload fault. |
| C05 | A car wash is a clean multi-step cyclic process: foam, brush, rinse and dry must run in order, and an emergency stop must abort the sequence safely. |
| C06 | Elevator doors combine limit switches, an obstacle detector and an automatic close timer; the obstacle must always win over a close command. |
| C07 | Height sorting is a realistic quality-gate task: an analog measurement must be filtered into accept/reject classes and the two streams counted independently. |
| C08 | Zone irrigation is a cyclic scheduling task with analog moisture thresholds; dry zones are watered in order and wet zones are skipped. |
| C09 | Zone accumulation is a core material-handling function: parts must queue without collision, and a blocked zone must raise a jam alarm instead of stalling silently. |
| C10 | Burner start-up is safety-critical: a purge must precede ignition, flame must be proven within a fixed window, and failure must latch a lockout. |
| C11 | Palletizing combines product counting, layer formation and a full-pallet handshake; it is a realistic batching and filtering problem. |
| C12 | Muting lets a pallet pass through a light curtain without tripping the safety stop, but only when two sensors confirm the correct sequence; a wrong sequence must alarm. |

## Diversity measurement

| Axis | Questions | Count |
| --- | --- | --- |
| sorting_filtering | C01, C07, C09, C11 | 4 |
| cyclic_timing | C03, C04, C05, C08 | 4 |
| safety_logic | C02, C06, C10, C12 | 4 |

Difficulty distribution:

| Difficulty | Questions | Count |
| --- | --- | --- |
| easy | C01, C02, C03 | 3 |
| medium | C04, C05, C06, C07, C08 | 5 |
| hard | C09, C10, C11, C12 | 4 |

Additional diversity: edge detection, timers, counters, analog thresholds, state machines, safety interlocks, jam detection and flame proving. The public bank mainly covers state machines and alarm/debounce logic, so this set deliberately emphasises sorting/filtering, cyclic timing and safety logic.

## Review process

Each question was checked for: deterministic I/O; a safe fail state; bounded timers; no unbounded loops; and testability in a 20 ms scan. Independent peer review is still pending.
