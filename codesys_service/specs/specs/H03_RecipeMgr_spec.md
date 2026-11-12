# H03_RecipeMgr · Recipe Management System — Formal Specification (LTL)

## Conventions
Each LTL state is the end of one scan cycle. `db` is the recipe database `ARRAY[1..10] OF ST_Recipe`; a slot is free when `recipeID = 0`. `exists(id)` means some slot holds that recipe number.



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
| P1 | Query hit | Querying an existing number outputs that recipe without error. | `G((queryRecipe AND exists(recipeIn.recipeID)) -> (NOT error AND recipeQueryResult = db[slot(recipeIn.recipeID)]))` |
| P2 | Query miss | Querying a missing number reports 16#8001. | `G((queryRecipe AND NOT exists(recipeIn.recipeID)) -> (error AND status = 16#8001))` |
| P3 | Add duplicate | Adding an existing number reports 16#8002 and does not modify the database. | `G((addRecipe AND exists(recipeIn.recipeID)) -> (error AND status = 16#8002 AND X db = db))` |
| P4 | Add full | Adding with no free slot reports 16#8003. | `G((addRecipe AND NOT exists(recipeIn.recipeID) AND noFreeSlot) -> (error AND status = 16#8003 AND X db = db))` |
| P5 | Add success | A valid add stores the recipe in the free slot with the smallest index. | `G((addRecipe AND NOT exists(recipeIn.recipeID) AND hasFreeSlot) -> (recipeAdded AND X db[minFreeIndex] = recipeIn))` |
| P6 | Delete miss | Deleting a missing number reports 16#8004. | `G((deleteRecipe AND NOT exists(recipeIn.recipeID)) -> (error AND status = 16#8004))` |
| P7 | Delete success | Deleting an existing number clears that slot (`recipeID := 0`). | `G((deleteRecipe AND exists(recipeIn.recipeID)) -> (recipeDeleted AND X db[slot].recipeID = 0))` |
| P8 | Modify miss | Modifying a missing number reports 16#8005. | `G((modifyRecipe AND NOT exists(recipeIn.recipeID)) -> (error AND status = 16#8005))` |
| P9 | Modify success | Modifying an existing number replaces that slot with the input recipe. | `G((modifyRecipe AND exists(recipeIn.recipeID)) -> (recipeModified AND X db[slot] = recipeIn))` |
| P10 | Uniqueness | Recipe numbers in the database are never duplicated. | `G(FORALL i <> j: (db[i].recipeID <> 0) -> db[i].recipeID <> db[j].recipeID)` |
| P11 | No request | Without a request the database is unchanged. | `G((NOT addRecipe AND NOT deleteRecipe AND NOT modifyRecipe AND NOT queryRecipe) -> X db = db)` |
| P12 | Query read-only | A query never modifies the database. | `G(queryRecipe -> X db = db)` |
| P13 | Error status | `status = 16#0000` whenever `error` is FALSE. | `G(NOT error -> status = 16#0000)` |

## Assumptions and requirement gaps
1. **Simultaneous requests** are not specified; the tests only ever assert one request at a time. ⚠️
2. **Request edge vs. level**: the requirement says "triggered"; the tests release the request between operations so that both readings behave identically.
3. **Success indicators** (`recipeAdded` etc.) are assumed to be TRUE in the cycle of a successful operation; their duration is not specified.
4. **`recipeQueryResult` after a failed query** is not specified and is not tested.
5. **Adding recipe number 0** is excluded, since 0 denotes an empty slot.

## Test cases

File: `H03_RecipeMgr.testcase.json` (3 cases, 23 scan cycles).

| Case | Purpose | Properties covered |
|---|---|---|
| TC01 | Add two recipes, duplicate rejected with 16#8002 | P3, P5, P10 |
| TC02 | Query hit returns all fields; query miss 16#8001 | P1, P2, P12 |
| TC03 | Modify, query verifies the change, 16#8005; delete, 16#8001 after delete, 16#8004 | P6–P9, P13 |

## Validation of the test cases

| Check | Result |
|---|---|
| Structural check (`dry`) | interface names and types match the declaration |
| Offline simulation (`sim`) vs the Part-4 reference implementation | **3/3 cases** — PASS |
| Offline simulation (`sim`) vs the Part-2 reference implementation | **3/3 cases** — PASS |
| CODESYS V3.5 compilation (FUNCTION_BLOCK) | PASS |
| Mutation testing (ST mutants) | **2/2** mutants detected |

Suite: 3 cases / 23 scan cycles.

The test cases were run against two independently written reference implementations; where their behaviour differed, the decision recorded in `CROSSCHECK.md` (section "Conventions settled") was adopted.

---

*Derived values in this section are regenerated from the test-case file and the run artefacts by `tools/sync_specs.py`; do not edit them by hand.*
