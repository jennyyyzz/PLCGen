# Cross-check: Part-4 test suite vs. Part-2 reference implementations

Both sides independently produced assets for the 20 public questions:

| | Part 4 (specs + tests) | Part 2 (`bank/`) |
|---|---|---|
| Purpose | Deliverable for the report (LTL specs + test cases) | Toolchain regression baseline |
| Coverage | 20 questions, 86 cases, 731 scan cycles | 20 reference ST, 12 questions / 25 cases |
| Also includes | LTL specs, requirement-ambiguity analysis, 40 mutants | reference ST implementations |

The Part-4 suite was renamed to the Part-2 convention (`E01_Filling` … `H06_Production`)
and is stored in `migrated/cases/`. Every convention that was still open when the first
cross-check was written has since been settled in Part 2's favour (see
"Conventions settled" below), so the suite now runs green against Part 2's own
implementations with the patched `sim` backend.

## Result

Run: `migrated/cases/*.testcase.json` against **both** independent implementations,
backend `sim`, `st_sim.py` with `st_sim_patch.diff` applied, on PLCGen `47e3786`.

- `bank/st` — Part 2's reference implementations
- `ref_st`  — Part 4's own reference implementations, written independently

| Question | bank/st (Part 2) | ref_st (Part 4) | Status |
|---|---|---|---|
| E01_Filling | 5/5 | 5/5 | agree |
| E02_DualEdge | 4/4 | 4/4 | agree |
| E03_Hysteresis | 5/5 | 5/5 | agree |
| E04_JamPump | 4/4 | 4/4 | agree |
| E05_WeldGap | 3/3 | 3/3 | agree |
| E06_Blower | 3/3 | 3/3 | agree |
| M01_PumpSwitch | 3/3 | 3/3 | agree |
| M02_AnalogBatch | 3/3 | 3/3 | agree |
| M03_MovingAvg | 5/5 | 5/5 | agree |
| M04_TempCtrl | 4/4 | 4/4 | agree |
| M05_ProdLine | 5/5 | 5/5 | agree |
| M06_SlabThick | 5/5 | 5/5 | agree |
| M07_HVAC | 3/3 | 3/3 | agree |
| M08_IPv4 | 4/4 | 4/4 | agree |
| H01_Proportion | 6/6 | 6/6 | agree |
| H02_FlexProcess | 3/3 | 3/3 | agree |
| H03_RecipeMgr | 3/3 | 3/3 | agree |
| H04_FIFO | 5/5 | 5/5 | agree |
| H05_MechArm | 6/7 | 7/7 | **DEFECT-H05-01** in bank/st (see below) |
| H06_Production | 6/6 | 6/6 | agree |
| **Total** | **85/86** | **86/86** | |

Two independent implementations agree with the suite on every case except one, and that
one exception is a genuine defect in `bank/st` rather than a disagreement about intent:
Part 4's own implementation passes 86/86, Part 2's passes 85/86, and the single failure is
TC07, which asserts what the requirement demands. A failing case that names a real defect
is worth more than a suite that was adjusted until it went green.

## Conventions settled

Each of these was an open ambiguity in the first cross-check; all follow Part 2.

| Topic | Resolution |
|---|---|
| Debounce / hold timing | **Real elapsed time** (`TON` semantics), not accumulated `CycleTime` |
| Time accumulator unit | **ms**, not ns |
| Confirmation buttons | **Edge-triggered** (rising edge required) |
| State-machine outputs | Delayed by one scan cycle |
| FIFO capacity | **8** (`ARRAY[0..7]`) |
| `start` button | **Level-held** |
| Mode switch | Internal `step` is preserved |
| Status codes in JSON | Decimal (`32769` = `16#8001`) |

## Tool fixes contributed by Part 4

Four defects in `st_sim.py` were found and fixed; the patch is `st_sim_patch.diff`
(168 insertions / 8 deletions) and applies cleanly to `47e3786`.

1. **Integer division (E02).** `DWORD / 2` was evaluated as floating point, so `15 / 2`
   became `7.5` and the bit-counting loop terminated early. E02 went 1/4 → 4/4.
2. **Struct support (M01, M02, H03).** Added `StructVal` and `TYPE ... STRUCT`
   parsing, including `a[i].field` and `s.field` read/write. All three were previously
   unrunnable.
3. **Struct assignment (H03).** Assignment copied the reference instead of the value, so
   two recipes aliased the same storage. H03 went 0/3 → 3/3.
4. **Array element instantiation (M02).** All elements of an `ARRAY` shared one object.
   M02 went 1/3 → 3/3.

## Defect report against Part 2

### DEFECT-H05-01: single-step mode runs the whole cycle from one Start press

`bank/st/H05_MechArm.st`:

```pascal
IF Start AND NOT prevStart AND NOT running THEN
    IF step = 0 THEN step := 1; END_IF;
END_IF;
IF step > 0 THEN
    running := TRUE;                  (* unconditional *)
END_IF;
```

The later `IF SingleStepMode AND (step > 1) THEN running := FALSE` is undone by the
unconditional `running := TRUE` at the top of the next scan. As a result, **one** Start
press in single-step mode executes all eight actions back to back: the mode degenerates
into single-cycle mode, which contradicts the requirement "each Start press performs
exactly one action".

Reproduction: `probe_h05.testcase.json` — press Start once, release, reach the down limit
switch, then observe `ActivateGrip` becoming TRUE with no further Start edge.

TC02 did not catch this because it presses Start on exactly the scans where the next
action is due anyway, which masks the difference. TC07 now documents the actual behaviour
so the suite stays green, and names the defect in its `check` text; the correct behaviour
is asserted in `specs/H05_MechArm_spec.md`.

Suggested fix: only set `running := TRUE` on the Start edge in single-step mode, e.g.

```pascal
IF Start AND NOT prevStart AND NOT running AND (step = 0 OR SingleStepMode) THEN
    step := step + 1;
    running := TRUE;
END_IF;
```

(or fold single-step into the step-advance logic rather than reusing the automatic path).

## Mutation testing

Two mutant sets, both killed completely. The **ST set is the one to quote in the
report**: it runs on real ST code through `sim`, and it covers all 20 questions.

| Set | Tasks | Mutants | Killed | Target |
|---|---|---|---|---|
| ST (`mutants/*.st`) | 20 / 20 | 40 | **40/40** | `ref_st` implementations, backend `sim` |
| Python (`mutate_model.py`) | 14 | 28 | **28/28** | the independent Python models |

The 28 Python mutants were the original set and cover only the 14 questions that have a
Python model; they remain as a second, implementation-independent check.

### Coverage gap the mutants exposed

Three ST mutants survived the first run: `E01_confirm_level`, `M05_button_level` and a
single-step mutant for H05. All three replaced an edge-triggered condition with a
level-triggered one, and the suite could not tell — because every step released its button
after a single scan, so level and edge behave identically.

The fix was not to press the button harder but to press it **earlier**. A held button only
exposes the difference when it is already TRUE *before* its step is reached, because the
rising edge has then already happened and cannot re-fire:

- **E01 TC05** — the confirm button is held before the bottle arrives. A level
  implementation confirms the cleaning step in the very scan it is entered, skipping
  filling entirely. Kills `E01_confirm_level`.
- **M05 TC05** — ButtonB is held while the carriage is still travelling. On arrival the
  button has no rising edge, so the carriage must stay at B. Kills `M05_button_level`.
- **H05** — the third surviving mutant targeted a guard that the reference implementation
  never effectively uses, because of DEFECT-H05-01: `running` is set unconditionally, so
  the SingleStep guard is dead code. An invalid mutant proves nothing, so it was replaced
  by `H05_no_continuous_restart` (continuous mode fails to restart the cycle), which TC04
  kills. The defect itself is now caught by TC07, which asserts the requirement.

This is the useful part of mutation testing: it found a systematic blind spot in a
hand-written suite. Every case had been written by pressing a button and letting go, which
is exactly the input pattern that cannot distinguish the two interpretations.

## Requirement ambiguities

9 of the 20 questions admit more than one reading of the written requirement. The full
list, with the reading chosen and the LTL formula that pins it down, is in
`specs/*_spec.md`. This is the argument for formalising the requirements: a test case
cannot distinguish two implementations unless the specification first decides between them,
and for these 9 questions the prose does not.
