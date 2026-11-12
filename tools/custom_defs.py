"""Definitions for the custom PLC question bank (C01-C12).

This module is intentionally data-only: build_custom.py turns it into the
question JSON, LTL specs, test cases, reference ST and documentation.
"""

def step(cycle, inputs, expect, check, hold_ms=None):
    s = {"cycle": cycle, "inputs": inputs, "expect": expect, "check": check}
    if hold_ms is not None:
        s["hold_ms"] = hold_ms
    return s


QUESTIONS = [
    {
        "id": "C01",
        "pou": "FB_C01",
        "title": "Product Reject and Filtering Station",
        "difficulty": "easy",
        "axis": "sorting_filtering",
        "tags": ["edge_detection", "counter", "timer", "batch", "reject"],
        "rationale": "A reject station is a common end-of-line filtering task: good and defective parts must be classified, counted and separated without stopping the conveyor until a batch is complete.",
        "requirements": """A conveyor transports parts past an inspection sensor. A part is defective when `DefectSensor` is TRUE while `PartPresent` is TRUE. The conveyor runs while `RunSwitch` is TRUE, unless the batch is complete. The batch size is 5 parts.

When a rising edge of `PartPresent` occurs while the conveyor is enabled:
- if `DefectSensor` is TRUE, count the part as rejected, activate `RejectPusher` for 1 s and then retract it;
- otherwise count the part as accepted.

When the total number of classified parts reaches 5, set `BatchFull` to TRUE and stop the conveyor. Pressing `ResetButton` clears both counters, clears `BatchFull` and allows a new batch. `RejectPusher` must never be active when `BatchFull` is TRUE.""",
        "interface": [
            ("RunSwitch", "input", "BOOL", "Enables the conveyor"),
            ("PartPresent", "input", "BOOL", "Part is present at the inspection point"),
            ("DefectSensor", "input", "BOOL", "TRUE when the present part is defective"),
            ("ResetButton", "input", "BOOL", "Clears counters and batch-full state"),
            ("ConveyorMotor", "output", "BOOL", "Conveyor drive command"),
            ("RejectPusher", "output", "BOOL", "Defective-part pusher command"),
            ("AcceptCount", "output", "INT", "Number of accepted parts in the batch"),
            ("RejectCount", "output", "INT", "Number of rejected parts in the batch"),
            ("BatchFull", "output", "BOOL", "Batch of 5 parts completed"),
        ],
        "atoms": [
            ("RunSwitch", "input", "RunSwitch", "Conveyor enabled"),
            ("PartPresent", "input", "PartPresent", "Part at inspection point"),
            ("DefectSensor", "input", "DefectSensor", "Defective part"),
            ("RejectPusher", "output", "RejectPusher", "Pusher extended"),
            ("BatchFull", "output", "BatchFull", "Batch complete"),
            ("ConveyorMotor", "output", "ConveyorMotor", "Conveyor running"),
        ],
        "specs": [
            ("P1", "Defective part is rejected", "G((PartPresent ∧ DefectSensor ∧ RunSwitch ∧ ¬BatchFull) → RejectPusher)", "A defective part on a running conveyor activates the pusher on the next scan."),
            ("P2", "Pusher retracts", "G(RejectPusher → F ¬RejectPusher)", "The reject pusher is a temporary pulse, not a permanent output."),
            ("P3", "Batch full stops the conveyor", "G(BatchFull → ¬ConveyorMotor)", "No further parts may be transported after the batch is full."),
        ],
        "cases": [
            {
                "id": "TC01",
                "name": "accept and reject a part",
                "coverage": "normal accept, defective reject, pusher time-out",
                "initial_state": "counters zero, batch not full",
                "steps": [
                    step(0, {"RunSwitch": 1, "PartPresent": 0, "DefectSensor": 0, "ResetButton": 1}, {"ConveyorMotor": 1, "AcceptCount": 0, "RejectCount": 0, "BatchFull": 0, "RejectPusher": 0}, "reset"),
                    step(1, {"ResetButton": 0, "PartPresent": 1, "DefectSensor": 0}, {"AcceptCount": 1, "RejectCount": 0, "RejectPusher": 0, "ConveyorMotor": 1}, "good part accepted"),
                    step(2, {"PartPresent": 0}, {"AcceptCount": 1, "RejectCount": 0, "RejectPusher": 0}, "part leaves"),
                    step(3, {"PartPresent": 1, "DefectSensor": 1}, {"AcceptCount": 1, "RejectCount": 1, "RejectPusher": 1, "ConveyorMotor": 1}, "defective part rejected"),
                    step(4, {"PartPresent": 0}, {"RejectCount": 1, "RejectPusher": 0}, "pusher retracted after 1 s", hold_ms=1100),
                ],
            },
            {
                "id": "TC02",
                "name": "batch of five stops the conveyor",
                "coverage": "five accepted parts, batch full, reset",
                "initial_state": "counters zero, batch not full",
                "steps": [
                    step(0, {"RunSwitch": 1, "ResetButton": 1, "PartPresent": 0}, {"AcceptCount": 0, "BatchFull": 0, "ConveyorMotor": 1}, "reset"),
                    step(1, {"ResetButton": 0, "PartPresent": 1}, {"AcceptCount": 1, "ConveyorMotor": 1}, "part 1"),
                    step(2, {"PartPresent": 0}, {"AcceptCount": 1}, "gap"),
                    step(3, {"PartPresent": 1}, {"AcceptCount": 2}, "part 2"),
                    step(4, {"PartPresent": 0}, {"AcceptCount": 2}, "gap"),
                    step(5, {"PartPresent": 1}, {"AcceptCount": 3}, "part 3"),
                    step(6, {"PartPresent": 0}, {"AcceptCount": 3}, "gap"),
                    step(7, {"PartPresent": 1}, {"AcceptCount": 4}, "part 4"),
                    step(8, {"PartPresent": 0}, {"AcceptCount": 4}, "gap"),
                    step(9, {"PartPresent": 1}, {"AcceptCount": 5, "BatchFull": 1, "ConveyorMotor": 0}, "fifth part fills batch"),
                    step(10, {"PartPresent": 0, "ResetButton": 1}, {"AcceptCount": 0, "RejectCount": 0, "BatchFull": 0, "ConveyorMotor": 1}, "reset starts a new batch"),
                ],
            },
        ],
        "st": """FUNCTION_BLOCK FB_C01
VAR_INPUT
    RunSwitch : BOOL;
    PartPresent : BOOL;
    DefectSensor : BOOL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    ConveyorMotor : BOOL;
    RejectPusher : BOOL;
    AcceptCount : INT;
    RejectCount : INT;
    BatchFull : BOOL;
END_VAR
VAR
    prevPart : BOOL;
    partEdge : BOOL;
    rejectPulse : BOOL;
    pusherTimer : TOF;
    total : INT;
END_VAR

partEdge := PartPresent AND NOT prevPart;
rejectPulse := partEdge AND DefectSensor AND RunSwitch AND NOT BatchFull;
pusherTimer(IN := rejectPulse, PT := T#1S);

IF ResetButton THEN
    AcceptCount := 0;
    RejectCount := 0;
    BatchFull := FALSE;
ELSIF partEdge AND RunSwitch AND NOT BatchFull THEN
    IF DefectSensor THEN
        RejectCount := RejectCount + 1;
    ELSE
        AcceptCount := AcceptCount + 1;
    END_IF;
    total := AcceptCount + RejectCount;
    IF total >= 5 THEN
        BatchFull := TRUE;
    END_IF;
END_IF;

ConveyorMotor := RunSwitch AND NOT BatchFull;
RejectPusher := pusherTimer.Q AND NOT BatchFull;
prevPart := PartPresent;
""",
    },
    {
        "id": "C02",
        "pou": "FB_C02",
        "title": "Two-Hand Safety Press",
        "difficulty": "easy",
        "axis": "safety_logic",
        "tags": ["safety_interlock", "anti_tiedown", "timer", "edge_detection"],
        "rationale": "Two-hand control prevents an operator from reaching into a press while it closes; the anti-tiedown timer catches a blocked or defeated button.",
        "requirements": """A press may close only when both operator buttons (`LeftButton`, `RightButton`) are held and a part is present (`PartPresent`). The press output `PressOutput` follows the two buttons while the safety conditions are satisfied.

Safety requirements:
- If one button is held alone for more than 500 ms, latch `Fault` to TRUE. While `Fault` is TRUE, `PressOutput` must remain FALSE.
- `ResetButton` clears `Fault` only when neither button is held.
- When `PressOutput` falls from TRUE to FALSE, emit a one-scan `CycleComplete` pulse.
- `PressOutput` must never be TRUE without `PartPresent`.""",
        "interface": [
            ("LeftButton", "input", "BOOL", "Left operator button"),
            ("RightButton", "input", "BOOL", "Right operator button"),
            ("PartPresent", "input", "BOOL", "Part is present in the press"),
            ("ResetButton", "input", "BOOL", "Clears the fault latch"),
            ("PressOutput", "output", "BOOL", "Press closes while TRUE"),
            ("CycleComplete", "output", "BOOL", "One-scan pulse after a press cycle"),
            ("Fault", "output", "BOOL", "Anti-tiedown fault latched"),
        ],
        "atoms": [
            ("LeftButton", "input", "LeftButton", "Left button pressed"),
            ("RightButton", "input", "RightButton", "Right button pressed"),
            ("PartPresent", "input", "PartPresent", "Part present"),
            ("PressOutput", "output", "PressOutput", "Press closing"),
            ("CycleComplete", "output", "CycleComplete", "Cycle finished"),
            ("Fault", "output", "Fault", "Fault latched"),
            ("LeftOnlyTimerQ", "internal", "leftTimer.Q", "Left button held alone for 500 ms"),
            ("RightOnlyTimerQ", "internal", "rightTimer.Q", "Right button held alone for 500 ms"),
        ],
        "specs": [
            ("P1", "Two-hand start", "G((LeftButton ∧ RightButton ∧ PartPresent ∧ ¬Fault) → PressOutput)", "Both buttons and a part command the press on the next scan."),
            ("P2", "Part interlock", "G(PressOutput → PartPresent)", "The press cannot close without a part."),
            ("P3", "Anti-tiedown detects a held button", "G((LeftOnlyTimerQ ∨ RightOnlyTimerQ) → F Fault)", "A single button held for 500 ms eventually latches the fault."),
        ],
        "cases": [
            {
                "id": "TC01",
                "name": "two-hand press and release",
                "coverage": "normal two-hand start, cycle-complete pulse, reset state",
                "initial_state": "no buttons, no part, no fault",
                "steps": [
                    step(0, {"LeftButton": 0, "RightButton": 0, "PartPresent": 0, "ResetButton": 1}, {"PressOutput": 0, "CycleComplete": 0, "Fault": 0}, "reset"),
                    step(1, {"ResetButton": 0, "LeftButton": 1, "RightButton": 1, "PartPresent": 1}, {"PressOutput": 1, "CycleComplete": 0, "Fault": 0}, "both buttons close the press"),
                    step(2, {"LeftButton": 0, "RightButton": 1, "PartPresent": 1}, {"PressOutput": 0, "CycleComplete": 1}, "release one button, cycle complete"),
                    step(3, {"LeftButton": 0, "RightButton": 0, "PartPresent": 0}, {"PressOutput": 0, "CycleComplete": 0}, "cycle pulse ends"),
                ],
            },
            {
                "id": "TC02",
                "name": "anti-tiedown fault",
                "coverage": "single button held 500 ms, fault latch, reset, restart",
                "initial_state": "no fault",
                "steps": [
                    step(0, {"LeftButton": 0, "RightButton": 0, "PartPresent": 0, "ResetButton": 1}, {"Fault": 0, "PressOutput": 0}, "reset"),
                    step(1, {"ResetButton": 0, "LeftButton": 1, "RightButton": 0}, {"Fault": 1, "PressOutput": 0}, "one button held alone", hold_ms=600),
                    step(2, {"LeftButton": 1, "RightButton": 1, "PartPresent": 1}, {"Fault": 1, "PressOutput": 0}, "fault blocks the press"),
                    step(3, {"LeftButton": 0, "RightButton": 0, "PartPresent": 0, "ResetButton": 1}, {"Fault": 0, "PressOutput": 0}, "reset while released"),
                    step(4, {"ResetButton": 0}, {"Fault": 0, "PressOutput": 0}, "buttons released"),
                    step(5, {"LeftButton": 1, "RightButton": 1, "PartPresent": 1}, {"Fault": 0, "PressOutput": 1}, "press can restart"),
                ],
            },
        ],
        "st": """FUNCTION_BLOCK FB_C02
VAR_INPUT
    LeftButton : BOOL;
    RightButton : BOOL;
    PartPresent : BOOL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    PressOutput : BOOL;
    CycleComplete : BOOL;
    Fault : BOOL;
END_VAR
VAR
    leftTimer : TON;
    rightTimer : TON;
    pressWasOn : BOOL;
END_VAR

leftTimer(IN := LeftButton AND NOT RightButton, PT := T#500MS);
rightTimer(IN := RightButton AND NOT LeftButton, PT := T#500MS);

IF leftTimer.Q OR rightTimer.Q THEN
    Fault := TRUE;
END_IF;

IF ResetButton AND NOT LeftButton AND NOT RightButton THEN
    Fault := FALSE;
END_IF;

PressOutput := LeftButton AND RightButton AND PartPresent AND NOT Fault;
CycleComplete := pressWasOn AND NOT PressOutput;
pressWasOn := PressOutput;
""",
    },
    {
        "id": "C03",
        "pou": "FB_C03",
        "title": "Automatic Barrier Gate",
        "difficulty": "easy",
        "axis": "cyclic_timing",
        "tags": ["timer", "edge_detection", "safety_beam", "access_control"],
        "rationale": "Vehicle barriers combine a short open command, a hold-open condition and a delayed close; the safety beam must reopen the gate at any time.",
        "requirements": """A vehicle barrier opens when `OpenButton` is pressed (rising edge), when a vehicle is detected (`VehiclePresent`), or when the safety beam is interrupted (`SafetyBeam`). The gate remains open while `VehiclePresent` or `SafetyBeam` is TRUE.

When the gate is open and there is no vehicle, no beam interruption and no open command, the gate closes automatically after 3 s. If `SafetyBeam` becomes TRUE while the gate is closed, the gate reopens immediately and `WarningLight` is TRUE. `WarningLight` follows `SafetyBeam`. `GateOpen` and `GateClosed` are mutually exclusive and describe the gate state.""",
        "interface": [
            ("VehiclePresent", "input", "BOOL", "Vehicle loop detector"),
            ("OpenButton", "input", "BOOL", "Manual open command"),
            ("SafetyBeam", "input", "BOOL", "Safety beam interrupted (obstacle)"),
            ("GateOpen", "output", "BOOL", "Gate is fully open"),
            ("GateClosed", "output", "BOOL", "Gate is fully closed"),
            ("WarningLight", "output", "BOOL", "Safety warning lamp"),
        ],
        "atoms": [
            ("VehiclePresent", "input", "VehiclePresent", "Vehicle detected"),
            ("OpenButton", "input", "OpenButton", "Open button pressed"),
            ("SafetyBeam", "input", "SafetyBeam", "Obstacle detected"),
            ("GateOpen", "output", "GateOpen", "Gate open"),
            ("GateClosed", "output", "GateClosed", "Gate closed"),
            ("WarningLight", "output", "WarningLight", "Warning lamp on"),
        ],
        "specs": [
            ("P1", "Vehicle opens the gate", "G(VehiclePresent → GateOpen)", "A detected vehicle must not be blocked by a closed gate."),
            ("P2", "Beam opens and warns", "G(SafetyBeam → (GateOpen ∧ WarningLight))", "An obstacle forces the gate open and lights the warning lamp."),
            ("P3", "Delayed close", "G((GateOpen ∧ ¬VehiclePresent ∧ ¬SafetyBeam) → F GateClosed)", "After the hold conditions disappear, the gate eventually closes."),
        ],
        "cases": [
            {
                "id": "TC01",
                "name": "open button and automatic close",
                "coverage": "manual open, 3 s close delay, closed state",
                "initial_state": "gate closed, no vehicle, no beam",
                "steps": [
                    step(0, {"VehiclePresent": 0, "OpenButton": 0, "SafetyBeam": 0}, {"GateOpen": 0, "GateClosed": 1, "WarningLight": 0}, "initial closed"),
                    step(1, {"OpenButton": 1}, {"GateOpen": 1, "GateClosed": 0, "WarningLight": 0}, "manual open"),
                    step(2, {"OpenButton": 0}, {"GateOpen": 1, "GateClosed": 0}, "no vehicle, close delay running"),
                    step(3, {}, {"GateOpen": 0, "GateClosed": 1}, "closed after 3 s", hold_ms=3100),
                ],
            },
            {
                "id": "TC02",
                "name": "vehicle and safety beam",
                "coverage": "hold open by vehicle, beam warning, reopen while closed",
                "initial_state": "gate closed",
                "steps": [
                    step(0, {"VehiclePresent": 1}, {"GateOpen": 1, "GateClosed": 0}, "vehicle opens gate"),
                    step(1, {"VehiclePresent": 0}, {"GateOpen": 1, "GateClosed": 0}, "vehicle leaves, close delay"),
                    step(2, {"SafetyBeam": 1}, {"GateOpen": 1, "WarningLight": 1}, "beam keeps gate open"),
                    step(3, {"SafetyBeam": 0}, {"GateOpen": 0, "GateClosed": 1, "WarningLight": 0}, "beam clear, close after 3 s", hold_ms=3100),
                    step(4, {"SafetyBeam": 1}, {"GateOpen": 1, "GateClosed": 0, "WarningLight": 1}, "beam reopens closed gate"),
                ],
            },
        ],
        "st": """FUNCTION_BLOCK FB_C03
VAR_INPUT
    VehiclePresent : BOOL;
    OpenButton : BOOL;
    SafetyBeam : BOOL;
END_VAR
VAR_OUTPUT
    GateOpen : BOOL;
    GateClosed : BOOL;
    WarningLight : BOOL;
END_VAR
VAR
    gateOpenState : BOOL;
    prevOpenButton : BOOL;
    closeTimer : TON;
END_VAR

IF ((OpenButton AND NOT prevOpenButton) OR VehiclePresent OR SafetyBeam) THEN
    gateOpenState := TRUE;
END_IF;

closeTimer(IN := gateOpenState AND NOT VehiclePresent AND NOT SafetyBeam AND NOT OpenButton, PT := T#3S);
IF closeTimer.Q THEN
    gateOpenState := FALSE;
END_IF;

GateOpen := gateOpenState;
GateClosed := NOT gateOpenState;
WarningLight := SafetyBeam;
prevOpenButton := OpenButton;
""",
    },
    {
        "id": "C04",
        "pou": "FB_C04",
        "title": "Star-Delta Motor Starter",
        "difficulty": "medium",
        "axis": "cyclic_timing",
        "tags": ["timer", "sequence", "motor_starting", "interlock", "fault_latch"],
        "rationale": "Star-delta starting is a standard motor-control sequence that requires a timed transition, contactor interlocking and a latched overload fault.",
        "requirements": """Implement a star-delta starter. A rising edge of `StartButton` energizes `MainContactor` and `StarContactor`. After 3 s the star contactor is de-energized and `DeltaContactor` is energized. `MainContactor` stays energized while the motor runs.

`StopButton` or `Overload` must stop the motor immediately. `Overload` latches `Fault`; `ResetButton` clears it only when `Overload` is FALSE. `StarContactor` and `DeltaContactor` must never be TRUE at the same time.""",
        "interface": [
            ("StartButton", "input", "BOOL", "Start command"),
            ("StopButton", "input", "BOOL", "Stop command"),
            ("Overload", "input", "BOOL", "Thermal overload trip"),
            ("ResetButton", "input", "BOOL", "Clears the fault latch"),
            ("MainContactor", "output", "BOOL", "Main contactor"),
            ("StarContactor", "output", "BOOL", "Star contactor"),
            ("DeltaContactor", "output", "BOOL", "Delta contactor"),
            ("Running", "output", "BOOL", "Motor is running"),
            ("Fault", "output", "BOOL", "Overload fault latched"),
        ],
        "atoms": [
            ("StartButton", "input", "StartButton", "Start command"),
            ("StopButton", "input", "StopButton", "Stop command"),
            ("Overload", "input", "Overload", "Overload trip"),
            ("MainContactor", "output", "MainContactor", "Main contactor closed"),
            ("StarContactor", "output", "StarContactor", "Star contactor closed"),
            ("DeltaContactor", "output", "DeltaContactor", "Delta contactor closed"),
            ("Fault", "output", "Fault", "Fault latched"),
        ],
        "specs": [
            ("P1", "Overload trips all contactors", "G(Overload → (¬MainContactor ∧ ¬StarContactor ∧ ¬DeltaContactor))", "An overload must remove power from every contactor."),
            ("P2", "Star-delta interlock", "G(¬(StarContactor ∧ DeltaContactor))", "The two contactors must never be closed together."),
            ("P3", "Timed transition", "G((MainContactor ∧ StarContactor) → F DeltaContactor)", "A running star connection eventually transitions to delta."),
        ],
        "cases": [
            {
                "id": "TC01",
                "name": "start, transition and stop",
                "coverage": "star start, 3 s transition, delta run, stop",
                "initial_state": "motor stopped",
                "steps": [
                    step(0, {"StartButton": 0, "StopButton": 0, "Overload": 0, "ResetButton": 0}, {"MainContactor": 0, "StarContactor": 0, "DeltaContactor": 0, "Running": 0}, "stopped"),
                    step(1, {"StartButton": 1}, {"MainContactor": 1, "StarContactor": 1, "DeltaContactor": 0, "Running": 1}, "star start"),
                    step(2, {"StartButton": 0}, {"MainContactor": 1, "StarContactor": 0, "DeltaContactor": 1, "Running": 1}, "delta after 3 s", hold_ms=3100),
                    step(3, {"StopButton": 1}, {"MainContactor": 0, "StarContactor": 0, "DeltaContactor": 0, "Running": 0}, "stop"),
                ],
            },
            {
                "id": "TC02",
                "name": "overload latch and reset",
                "coverage": "overload during delta, fault latch, reset, restart",
                "initial_state": "motor stopped",
                "steps": [
                    step(0, {"StartButton": 1}, {"MainContactor": 1, "StarContactor": 1}, "start"),
                    step(1, {"StartButton": 0}, {"MainContactor": 1, "DeltaContactor": 1}, "delta", hold_ms=3100),
                    step(2, {"Overload": 1}, {"MainContactor": 0, "StarContactor": 0, "DeltaContactor": 0, "Fault": 1, "Running": 0}, "overload trip"),
                    step(3, {"Overload": 0, "ResetButton": 1}, {"Fault": 0}, "reset"),
                    step(4, {"ResetButton": 0, "StartButton": 1}, {"MainContactor": 1, "StarContactor": 1}, "restart"),
                ],
            },
        ],
        "st": """FUNCTION_BLOCK FB_C04
VAR_INPUT
    StartButton : BOOL;
    StopButton : BOOL;
    Overload : BOOL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    MainContactor : BOOL;
    StarContactor : BOOL;
    DeltaContactor : BOOL;
    Running : BOOL;
    Fault : BOOL;
END_VAR
VAR
    prevStart : BOOL;
    startEdge : BOOL;
    starTimer : TON;
END_VAR

startEdge := StartButton AND NOT prevStart;

IF Overload THEN
    Fault := TRUE;
END_IF;
IF ResetButton AND NOT Overload THEN
    Fault := FALSE;
END_IF;

IF Fault OR StopButton THEN
    MainContactor := FALSE;
    StarContactor := FALSE;
    DeltaContactor := FALSE;
    Running := FALSE;
    starTimer(IN := FALSE, PT := T#3S);
ELSIF startEdge THEN
    MainContactor := TRUE;
    StarContactor := TRUE;
    DeltaContactor := FALSE;
    Running := TRUE;
    starTimer(IN := TRUE, PT := T#3S);
ELSE
    IF MainContactor THEN
        starTimer(IN := StarContactor, PT := T#3S);
        IF starTimer.Q THEN
            StarContactor := FALSE;
            DeltaContactor := TRUE;
        END_IF;
    END_IF;
END_IF;

prevStart := StartButton;
""",
    },
    {
        "id": "C05",
        "pou": "FB_C05",
        "title": "Car Wash Sequence",
        "difficulty": "medium",
        "axis": "cyclic_timing",
        "tags": ["state_machine", "timer", "sequence", "emergency_stop"],
        "rationale": "A car wash is a clean multi-step cyclic process: foam, brush, rinse and dry must run in order, and an emergency stop must abort the sequence safely.",
        "requirements": """A car wash cycle starts on a rising edge of `StartButton` when `VehiclePresent` is TRUE. The cycle is:
1. conveyor and foam for 2 s;
2. conveyor and brush for 2 s;
3. conveyor and rinse for 1 s;
4. conveyor and dry fan for 1 s;
then the conveyor stops and `CycleComplete` is TRUE.

`EmergencyStop` immediately switches off all actuators and latches `Fault`; `ResetButton` clears the fault. A new cycle cannot start while `Fault` is TRUE. `CycleComplete` is cleared by `ResetButton` or by a new start.""",
        "interface": [
            ("StartButton", "input", "BOOL", "Starts a wash cycle"),
            ("EmergencyStop", "input", "BOOL", "Emergency stop"),
            ("VehiclePresent", "input", "BOOL", "Vehicle in the wash bay"),
            ("ResetButton", "input", "BOOL", "Clears the emergency fault"),
            ("ConveyorMotor", "output", "BOOL", "Conveyor drive"),
            ("FoamValve", "output", "BOOL", "Foam valve"),
            ("BrushMotor", "output", "BOOL", "Brush motor"),
            ("RinseValve", "output", "BOOL", "Rinse valve"),
            ("DryFan", "output", "BOOL", "Dry fan"),
            ("CycleComplete", "output", "BOOL", "Wash cycle finished"),
            ("Fault", "output", "BOOL", "Emergency fault latched"),
        ],
        "atoms": [
            ("StartButton", "input", "StartButton", "Start command"),
            ("EmergencyStop", "input", "EmergencyStop", "Emergency stop"),
            ("VehiclePresent", "input", "VehiclePresent", "Vehicle present"),
            ("ConveyorMotor", "output", "ConveyorMotor", "Conveyor running"),
            ("FoamValve", "output", "FoamValve", "Foam active"),
            ("BrushMotor", "output", "BrushMotor", "Brush active"),
            ("RinseValve", "output", "RinseValve", "Rinse active"),
            ("DryFan", "output", "DryFan", "Dry fan active"),
            ("CycleComplete", "output", "CycleComplete", "Cycle finished"),
            ("Fault", "output", "Fault", "Fault latched"),
        ],
        "specs": [
            ("P1", "Emergency stop removes all actuators", "G(EmergencyStop → ¬(ConveyorMotor ∨ FoamValve ∨ BrushMotor ∨ RinseValve ∨ DryFan))", "Safety stop must de-energize every actuator on the next scan."),
            ("P2", "Foam requires conveyor", "G(FoamValve → ConveyorMotor)", "A wash chemical must not be applied without part motion."),
            ("P3", "Cycle eventually completes", "G((StartButton ∧ VehiclePresent ∧ ¬Fault) → F CycleComplete)", "A started wash cycle reaches its terminal state."),
        ],
        "cases": [
            {
                "id": "TC01",
                "name": "full wash sequence",
                "coverage": "foam, brush, rinse, dry, cycle complete",
                "initial_state": "idle, vehicle present",
                "steps": [
                    step(0, {"StartButton": 0, "EmergencyStop": 0, "VehiclePresent": 0, "ResetButton": 1}, {"ConveyorMotor": 0, "CycleComplete": 0, "Fault": 0}, "reset"),
                    step(1, {"ResetButton": 0, "StartButton": 1, "VehiclePresent": 1}, {"ConveyorMotor": 1, "FoamValve": 1, "BrushMotor": 0, "CycleComplete": 0}, "foam step"),
                    step(2, {"StartButton": 0}, {"ConveyorMotor": 1, "FoamValve": 0, "BrushMotor": 1}, "brush step", hold_ms=2100),
                    step(3, {}, {"ConveyorMotor": 1, "BrushMotor": 0, "RinseValve": 1}, "rinse step", hold_ms=2100),
                    step(4, {}, {"ConveyorMotor": 1, "RinseValve": 0, "DryFan": 1}, "dry step", hold_ms=1100),
                    step(5, {}, {"ConveyorMotor": 0, "DryFan": 0, "CycleComplete": 1}, "cycle complete", hold_ms=1100),
                ],
            },
            {
                "id": "TC02",
                "name": "emergency stop and reset",
                "coverage": "emergency during foam, fault latch, reset, restart",
                "initial_state": "idle",
                "steps": [
                    step(0, {"StartButton": 1, "VehiclePresent": 1}, {"ConveyorMotor": 1, "FoamValve": 1, "Fault": 0}, "cycle starts"),
                    step(1, {"StartButton": 0, "EmergencyStop": 1}, {"ConveyorMotor": 0, "FoamValve": 0, "Fault": 1}, "emergency stop"),
                    step(2, {"EmergencyStop": 0}, {"ConveyorMotor": 0, "Fault": 1}, "fault remains latched"),
                    step(3, {"ResetButton": 1}, {"Fault": 0, "ConveyorMotor": 0}, "reset"),
                    step(4, {"ResetButton": 0, "StartButton": 1}, {"ConveyorMotor": 1, "FoamValve": 1}, "restart"),
                ],
            },
        ],
        "st": """FUNCTION_BLOCK FB_C05
VAR_INPUT
    StartButton : BOOL;
    EmergencyStop : BOOL;
    VehiclePresent : BOOL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    ConveyorMotor : BOOL;
    FoamValve : BOOL;
    BrushMotor : BOOL;
    RinseValve : BOOL;
    DryFan : BOOL;
    CycleComplete : BOOL;
    Fault : BOOL;
END_VAR
VAR
    step : INT;
    prevStart : BOOL;
    startEdge : BOOL;
    foamTimer : TON;
    brushTimer : TON;
    rinseTimer : TON;
    dryTimer : TON;
END_VAR

startEdge := StartButton AND NOT prevStart;
foamTimer(IN := (step = 1), PT := T#2S);
brushTimer(IN := (step = 2), PT := T#2S);
rinseTimer(IN := (step = 3), PT := T#1S);
dryTimer(IN := (step = 4), PT := T#1S);

IF EmergencyStop THEN
    Fault := TRUE;
    step := 0;
END_IF;
IF ResetButton THEN
    Fault := FALSE;
    CycleComplete := FALSE;
END_IF;

IF startEdge AND VehiclePresent AND NOT Fault AND NOT EmergencyStop THEN
    step := 1;
    CycleComplete := FALSE;
END_IF;

IF step = 1 AND foamTimer.Q THEN
    step := 2;
END_IF;
IF step = 2 AND brushTimer.Q THEN
    step := 3;
END_IF;
IF step = 3 AND rinseTimer.Q THEN
    step := 4;
END_IF;
IF step = 4 AND dryTimer.Q THEN
    step := 5;
END_IF;
IF step = 5 THEN
    step := 0;
    CycleComplete := TRUE;
END_IF;

ConveyorMotor := (step >= 1) AND (step <= 4) AND NOT EmergencyStop AND NOT Fault;
FoamValve := (step = 1) AND NOT EmergencyStop AND NOT Fault;
BrushMotor := (step = 2) AND NOT EmergencyStop AND NOT Fault;
RinseValve := (step = 3) AND NOT EmergencyStop AND NOT Fault;
DryFan := (step = 4) AND NOT EmergencyStop AND NOT Fault;
prevStart := StartButton;
""",
    },
    {
        "id": "C06",
        "pou": "FB_C06",
        "title": "Elevator Door Control",
        "difficulty": "medium",
        "axis": "safety_logic",
        "tags": ["safety_interlock", "timer", "door_control", "limit_switch"],
        "rationale": "Elevator doors combine limit switches, an obstacle detector and an automatic close timer; the obstacle must always win over a close command.",
        "requirements": """Control an elevator door with open and close commands. `DoorOpen` and `DoorClosed` report the limit switches. `OpenButton` starts opening; `CloseButton` starts closing only while `ObstacleSensor` is FALSE.

If the door is open with no obstacle, no open command and no close command, it closes automatically after 5 s. If `ObstacleSensor` is TRUE, the door must never close and `WarningBuzzer` is TRUE. If the obstacle appears while closing, the door reverses to opening. Both limit switches TRUE is an invalid state: latch `Fault`, stop the motors, and clear it with `ResetButton`.""",
        "interface": [
            ("OpenButton", "input", "BOOL", "Open door command"),
            ("CloseButton", "input", "BOOL", "Close door command"),
            ("ObstacleSensor", "input", "BOOL", "Obstacle in the door path"),
            ("DoorOpenLimit", "input", "BOOL", "Door fully open limit switch"),
            ("DoorClosedLimit", "input", "BOOL", "Door fully closed limit switch"),
            ("ResetButton", "input", "BOOL", "Clears the invalid-limit fault"),
            ("DoorMotorOpen", "output", "BOOL", "Open motor"),
            ("DoorMotorClose", "output", "BOOL", "Close motor"),
            ("DoorOpen", "output", "BOOL", "Door is open"),
            ("DoorClosed", "output", "BOOL", "Door is closed"),
            ("WarningBuzzer", "output", "BOOL", "Obstacle warning"),
            ("Fault", "output", "BOOL", "Invalid limit state latched"),
        ],
        "atoms": [
            ("OpenButton", "input", "OpenButton", "Open command"),
            ("CloseButton", "input", "CloseButton", "Close command"),
            ("ObstacleSensor", "input", "ObstacleSensor", "Obstacle detected"),
            ("DoorOpenLimit", "input", "DoorOpenLimit", "Open limit reached"),
            ("DoorClosedLimit", "input", "DoorClosedLimit", "Closed limit reached"),
            ("DoorMotorOpen", "output", "DoorMotorOpen", "Opening motor"),
            ("DoorMotorClose", "output", "DoorMotorClose", "Closing motor"),
            ("DoorOpen", "output", "DoorOpen", "Door open"),
            ("DoorClosed", "output", "DoorClosed", "Door closed"),
            ("Fault", "output", "Fault", "Fault latched"),
        ],
        "specs": [
            ("P1", "Obstacle prevents closing", "G(ObstacleSensor → ¬DoorMotorClose)", "The obstacle detector has priority over the close command."),
            ("P2", "Motor interlock", "G(¬(DoorMotorOpen ∧ DoorMotorClose))", "Open and close motors must never be energized together."),
            ("P3", "Automatic close", "G((DoorOpenLimit ∧ ¬ObstacleSensor ∧ ¬OpenButton) → F DoorMotorClose)", "An open door eventually starts closing when the path is clear."),
        ],
        "cases": [
            {
                "id": "TC01",
                "name": "open, close by button, limit stop",
                "coverage": "open command, open limit, close command, closed limit",
                "initial_state": "door closed",
                "steps": [
                    step(0, {"OpenButton": 0, "CloseButton": 0, "ObstacleSensor": 0, "DoorOpenLimit": 0, "DoorClosedLimit": 1, "ResetButton": 0}, {"DoorMotorOpen": 0, "DoorMotorClose": 0, "DoorClosed": 1, "DoorOpen": 0}, "closed"),
                    step(1, {"OpenButton": 1, "DoorClosedLimit": 0}, {"DoorMotorOpen": 1, "DoorMotorClose": 0}, "opening"),
                    step(2, {"OpenButton": 0, "DoorOpenLimit": 1}, {"DoorMotorOpen": 0, "DoorOpen": 1, "DoorClosed": 0}, "open limit"),
                    step(3, {"CloseButton": 1, "DoorOpenLimit": 1}, {"DoorMotorClose": 1, "DoorMotorOpen": 0}, "closing"),
                    step(4, {"CloseButton": 0, "DoorOpenLimit": 0, "DoorClosedLimit": 1}, {"DoorMotorClose": 0, "DoorClosed": 1}, "closed limit"),
                ],
            },
            {
                "id": "TC02",
                "name": "obstacle reversal and buzzer",
                "coverage": "closing, obstacle, reopen, buzzer",
                "initial_state": "door open",
                "steps": [
                    step(0, {"DoorOpenLimit": 1, "DoorClosedLimit": 0, "ObstacleSensor": 0}, {"DoorOpen": 1, "DoorMotorClose": 0}, "open"),
                    step(1, {"CloseButton": 1}, {"DoorMotorClose": 1, "DoorMotorOpen": 0}, "closing"),
                    step(2, {"ObstacleSensor": 1, "DoorOpenLimit": 0}, {"DoorMotorClose": 0, "DoorMotorOpen": 1, "WarningBuzzer": 1}, "obstacle reverses"),
                    step(3, {"ObstacleSensor": 0, "CloseButton": 0, "DoorOpenLimit": 1}, {"DoorMotorOpen": 0, "WarningBuzzer": 0, "DoorOpen": 1}, "open limit reached"),
                ],
            },
            {
                "id": "TC03",
                "name": "automatic close after 5 s",
                "coverage": "open door, no commands, auto close timer",
                "initial_state": "door open, path clear",
                "steps": [
                    step(0, {"DoorOpenLimit": 1, "DoorClosedLimit": 0, "OpenButton": 0, "CloseButton": 0, "ObstacleSensor": 0}, {"DoorMotorClose": 1, "DoorMotorOpen": 0}, "auto close starts after 5 s", hold_ms=5100),
                ],
            },
        ],
        "st": """FUNCTION_BLOCK FB_C06
VAR_INPUT
    OpenButton : BOOL;
    CloseButton : BOOL;
    ObstacleSensor : BOOL;
    DoorOpenLimit : BOOL;
    DoorClosedLimit : BOOL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    DoorMotorOpen : BOOL;
    DoorMotorClose : BOOL;
    DoorOpen : BOOL;
    DoorClosed : BOOL;
    WarningBuzzer : BOOL;
    Fault : BOOL;
END_VAR
VAR
    opening : BOOL;
    closing : BOOL;
    autoTimer : TON;
END_VAR

IF DoorOpenLimit AND DoorClosedLimit THEN
    Fault := TRUE;
    opening := FALSE;
    closing := FALSE;
ELSIF ResetButton THEN
    Fault := FALSE;
END_IF;

IF NOT Fault THEN
    IF (OpenButton AND NOT DoorOpenLimit) OR (ObstacleSensor AND closing) THEN
        opening := TRUE;
        closing := FALSE;
    END_IF;

    IF CloseButton AND NOT ObstacleSensor AND NOT OpenButton THEN
        closing := TRUE;
        opening := FALSE;
    END_IF;

    autoTimer(IN := DoorOpenLimit AND NOT ObstacleSensor AND NOT OpenButton AND NOT CloseButton, PT := T#5S);
    IF autoTimer.Q AND NOT ObstacleSensor THEN
        closing := TRUE;
        opening := FALSE;
    END_IF;

    IF ObstacleSensor THEN
        opening := TRUE;
        closing := FALSE;
    END_IF;

    IF opening AND DoorOpenLimit THEN
        opening := FALSE;
    END_IF;
    IF closing AND DoorClosedLimit THEN
        closing := FALSE;
    END_IF;
ELSE
    opening := FALSE;
    closing := FALSE;
    autoTimer(IN := FALSE, PT := T#5S);
END_IF;

DoorMotorOpen := opening;
DoorMotorClose := closing;
DoorOpen := DoorOpenLimit;
DoorClosed := DoorClosedLimit;
WarningBuzzer := ObstacleSensor;
""",
    },
    {
        "id": "C07",
        "pou": "FB_C07",
        "title": "Bottle Height Sorting",
        "difficulty": "medium",
        "axis": "sorting_filtering",
        "tags": ["analog_threshold", "sorting", "counter", "timer", "fault"],
        "rationale": "Height sorting is a realistic quality-gate task: an analog measurement must be filtered into accept/reject classes and the two streams counted independently.",
        "requirements": """A conveyor moves bottles past an analog height sensor. When a rising edge of `PartPresent` occurs while `RunSwitch` is TRUE, classify `HeightSensor`:
- 40.0 to 60.0 inclusive: accepted bottle; pulse `AcceptGate` for 500 ms and increment `AcceptCount`;
- outside that range: rejected bottle; pulse `RejectGate` for 500 ms and increment `RejectCount`.

A sensor value below 0.0 or above 100.0 is invalid: latch `Fault`, stop the conveyor and inhibit both gates. `ResetButton` clears the counters and the fault. `AcceptGate` and `RejectGate` must never be TRUE together.""",
        "interface": [
            ("RunSwitch", "input", "BOOL", "Enables the conveyor"),
            ("PartPresent", "input", "BOOL", "Bottle at the height sensor"),
            ("HeightSensor", "input", "REAL", "Measured bottle height in mm"),
            ("ResetButton", "input", "BOOL", "Clears counters and fault"),
            ("ConveyorMotor", "output", "BOOL", "Conveyor drive"),
            ("AcceptGate", "output", "BOOL", "Accept diverter gate"),
            ("RejectGate", "output", "BOOL", "Reject diverter gate"),
            ("AcceptCount", "output", "INT", "Accepted bottle count"),
            ("RejectCount", "output", "INT", "Rejected bottle count"),
            ("Fault", "output", "BOOL", "Invalid sensor value latched"),
        ],
        "atoms": [
            ("RunSwitch", "input", "RunSwitch", "Conveyor enabled"),
            ("PartPresent", "input", "PartPresent", "Bottle present"),
            ("HeightInRange", "derived", "HeightSensor >= 40.0 AND HeightSensor <= 60.0", "Height inside the accept window"),
            ("HeightOutOfRange", "derived", "(HeightSensor < 40.0 OR HeightSensor > 60.0) AND HeightSensor >= 0.0 AND HeightSensor <= 100.0", "Height outside the accept window but within sensor range"),
            ("AcceptGate", "output", "AcceptGate", "Accept gate active"),
            ("RejectGate", "output", "RejectGate", "Reject gate active"),
            ("Fault", "output", "Fault", "Fault latched"),
        ],
        "specs": [
            ("P1", "In-range bottle is accepted", "G((PartPresent ∧ HeightInRange ∧ RunSwitch ∧ ¬Fault) → AcceptGate)", "A valid height opens the accept gate on the next scan."),
            ("P2", "Out-of-range bottle is rejected", "G((PartPresent ∧ HeightOutOfRange ∧ RunSwitch ∧ ¬Fault) → RejectGate)", "A valid but wrong height opens the reject gate."),
            ("P3", "Gates are mutually exclusive", "G(¬(AcceptGate ∧ RejectGate))", "A bottle cannot be routed to both outputs."),
        ],
        "cases": [
            {
                "id": "TC01",
                "name": "accept and reject bottles",
                "coverage": "in-range accept, high reject, gate pulse 500 ms",
                "initial_state": "counters zero, conveyor enabled",
                "steps": [
                    step(0, {"RunSwitch": 1, "PartPresent": 0, "HeightSensor": 50.0, "ResetButton": 1}, {"ConveyorMotor": 1, "AcceptCount": 0, "RejectCount": 0, "Fault": 0}, "reset"),
                    step(1, {"ResetButton": 0, "PartPresent": 1, "HeightSensor": 50.0}, {"AcceptGate": 1, "RejectGate": 0, "AcceptCount": 1, "ConveyorMotor": 1}, "accept 50 mm"),
                    step(2, {"PartPresent": 0}, {"AcceptGate": 0, "AcceptCount": 1}, "accept gate retracts", hold_ms=600),
                    step(3, {"PartPresent": 1, "HeightSensor": 70.0}, {"AcceptGate": 0, "RejectGate": 1, "RejectCount": 1}, "reject 70 mm"),
                    step(4, {"PartPresent": 0}, {"RejectGate": 0, "RejectCount": 1}, "reject gate retracts", hold_ms=600),
                ],
            },
            {
                "id": "TC02",
                "name": "invalid sensor value",
                "coverage": "out-of-range sensor latches fault and inhibits gates",
                "initial_state": "counters zero",
                "steps": [
                    step(0, {"RunSwitch": 1, "PartPresent": 0, "HeightSensor": 50.0, "ResetButton": 1}, {"Fault": 0, "ConveyorMotor": 1}, "reset"),
                    step(1, {"ResetButton": 0, "PartPresent": 1, "HeightSensor": 150.0}, {"Fault": 1, "ConveyorMotor": 0, "AcceptGate": 0, "RejectGate": 0, "AcceptCount": 0, "RejectCount": 0}, "invalid height"),
                    step(2, {"ResetButton": 1, "HeightSensor": 50.0}, {"Fault": 0, "AcceptCount": 0, "RejectCount": 0, "ConveyorMotor": 1}, "reset"),
                ],
            },
        ],
        "st": """FUNCTION_BLOCK FB_C07
VAR_INPUT
    RunSwitch : BOOL;
    PartPresent : BOOL;
    HeightSensor : REAL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    ConveyorMotor : BOOL;
    AcceptGate : BOOL;
    RejectGate : BOOL;
    AcceptCount : INT;
    RejectCount : INT;
    Fault : BOOL;
END_VAR
VAR
    prevPart : BOOL;
    partEdge : BOOL;
    acceptPulse : BOOL;
    rejectPulse : BOOL;
    acceptTimer : TOF;
    rejectTimer : TOF;
END_VAR

IF (HeightSensor < 0.0) OR (HeightSensor > 100.0) THEN
    Fault := TRUE;
END_IF;
IF ResetButton THEN
    AcceptCount := 0;
    RejectCount := 0;
    Fault := FALSE;
END_IF;

partEdge := PartPresent AND NOT prevPart;
acceptPulse := partEdge AND RunSwitch AND NOT Fault AND (HeightSensor >= 40.0) AND (HeightSensor <= 60.0);
rejectPulse := partEdge AND RunSwitch AND NOT Fault AND ((HeightSensor < 40.0) OR (HeightSensor > 60.0));

acceptTimer(IN := acceptPulse, PT := T#500MS);
rejectTimer(IN := rejectPulse, PT := T#500MS);
AcceptGate := acceptTimer.Q;
RejectGate := rejectTimer.Q;

IF acceptPulse THEN
    AcceptCount := AcceptCount + 1;
ELSIF rejectPulse THEN
    RejectCount := RejectCount + 1;
END_IF;

ConveyorMotor := RunSwitch AND NOT Fault;
prevPart := PartPresent;
""",
    },
    {
        "id": "C08",
        "pou": "FB_C08",
        "title": "Greenhouse Irrigation Zones",
        "difficulty": "medium",
        "axis": "cyclic_timing",
        "tags": ["sequence", "timer", "analog_threshold", "scheduling", "stop"],
        "rationale": "Zone irrigation is a cyclic scheduling task with analog moisture thresholds; dry zones are watered in order and wet zones are skipped.",
        "requirements": """An irrigation cycle starts on a rising edge of `StartButton`. Three zones are visited in order. For each zone, if its moisture is below 30.0, open its valve and run `Pump` for 3 s; if the moisture is 30.0 or higher, skip the zone immediately.

After zone 3 the cycle ends: all valves and the pump are OFF and `CycleComplete` is TRUE. `StopButton` aborts the cycle immediately and clears `CycleComplete`. `ResetButton` clears `CycleComplete`. The pump must run whenever any zone valve is open.""",
        "interface": [
            ("StartButton", "input", "BOOL", "Starts an irrigation cycle"),
            ("StopButton", "input", "BOOL", "Aborts the cycle"),
            ("Zone1Moisture", "input", "REAL", "Soil moisture of zone 1"),
            ("Zone2Moisture", "input", "REAL", "Soil moisture of zone 2"),
            ("Zone3Moisture", "input", "REAL", "Soil moisture of zone 3"),
            ("ResetButton", "input", "BOOL", "Clears cycle-complete state"),
            ("Zone1Valve", "output", "BOOL", "Zone 1 valve"),
            ("Zone2Valve", "output", "BOOL", "Zone 2 valve"),
            ("Zone3Valve", "output", "BOOL", "Zone 3 valve"),
            ("Pump", "output", "BOOL", "Irrigation pump"),
            ("CycleComplete", "output", "BOOL", "All zones processed"),
        ],
        "atoms": [
            ("StartButton", "input", "StartButton", "Start command"),
            ("StopButton", "input", "StopButton", "Stop command"),
            ("Zone1Valve", "output", "Zone1Valve", "Zone 1 irrigating"),
            ("Zone2Valve", "output", "Zone2Valve", "Zone 2 irrigating"),
            ("Zone3Valve", "output", "Zone3Valve", "Zone 3 irrigating"),
            ("Pump", "output", "Pump", "Pump running"),
            ("CycleComplete", "output", "CycleComplete", "Cycle finished"),
        ],
        "specs": [
            ("P1", "Valve implies pump", "G((Zone1Valve ∨ Zone2Valve ∨ Zone3Valve) → Pump)", "The pump must run for any open zone valve."),
            ("P2", "Stop removes all outputs", "G(StopButton → ¬(Zone1Valve ∨ Zone2Valve ∨ Zone3Valve ∨ Pump))", "Stop must abort the cycle and de-energize the hydraulics."),
            ("P3", "Started cycle terminates", "G((StartButton ∧ ¬CycleComplete) → F CycleComplete)", "A cycle that is started eventually completes."),
        ],
        "cases": [
            {
                "id": "TC01",
                "name": "dry, wet, dry zones",
                "coverage": "zone 1 waters, zone 2 skipped, zone 3 waters, complete",
                "initial_state": "idle, zone 1 and 3 dry",
                "steps": [
                    step(0, {"StartButton": 1, "StopButton": 0, "Zone1Moisture": 20.0, "Zone2Moisture": 50.0, "Zone3Moisture": 20.0, "ResetButton": 1}, {"Zone1Valve": 1, "Pump": 1, "CycleComplete": 0}, "zone 1 starts"),
                    step(1, {"StartButton": 0, "ResetButton": 0}, {"Zone1Valve": 0, "Zone2Valve": 0, "Zone3Valve": 1, "Pump": 1}, "zone 2 skipped, zone 3 starts", hold_ms=3100),
                    step(2, {}, {"Zone3Valve": 0, "Pump": 0, "CycleComplete": 1}, "cycle complete", hold_ms=3100),
                    step(3, {"ResetButton": 1}, {"CycleComplete": 0, "Pump": 0}, "reset complete flag"),
                ],
            },
            {
                "id": "TC02",
                "name": "all zones wet",
                "coverage": "all zones skipped, immediate completion",
                "initial_state": "idle",
                "steps": [
                    step(0, {"StartButton": 1, "Zone1Moisture": 50.0, "Zone2Moisture": 50.0, "Zone3Moisture": 50.0}, {"Zone1Valve": 0, "Zone2Valve": 0, "Zone3Valve": 0, "Pump": 0, "CycleComplete": 1}, "all wet, complete immediately"),
                ],
            },
            {
                "id": "TC03",
                "name": "stop aborts irrigation",
                "coverage": "stop during zone 1, outputs off, complete cleared",
                "initial_state": "idle",
                "steps": [
                    step(0, {"StartButton": 1, "Zone1Moisture": 20.0}, {"Zone1Valve": 1, "Pump": 1}, "zone 1 starts"),
                    step(1, {"StartButton": 0, "StopButton": 1}, {"Zone1Valve": 0, "Pump": 0, "CycleComplete": 0}, "stop aborts"),
                ],
            },
        ],
        "st": """FUNCTION_BLOCK FB_C08
VAR_INPUT
    StartButton : BOOL;
    StopButton : BOOL;
    Zone1Moisture : REAL;
    Zone2Moisture : REAL;
    Zone3Moisture : REAL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    Zone1Valve : BOOL;
    Zone2Valve : BOOL;
    Zone3Valve : BOOL;
    Pump : BOOL;
    CycleComplete : BOOL;
END_VAR
VAR
    step : INT;
    prevStart : BOOL;
    startEdge : BOOL;
    zone1Timer : TON;
    zone2Timer : TON;
    zone3Timer : TON;
END_VAR

startEdge := StartButton AND NOT prevStart;
zone1Timer(IN := (step = 1) AND (Zone1Moisture < 30.0), PT := T#3S);
zone2Timer(IN := (step = 2) AND (Zone2Moisture < 30.0), PT := T#3S);
zone3Timer(IN := (step = 3) AND (Zone3Moisture < 30.0), PT := T#3S);

IF StopButton THEN
    step := 0;
    CycleComplete := FALSE;
END_IF;
IF ResetButton THEN
    CycleComplete := FALSE;
END_IF;
IF startEdge AND NOT CycleComplete AND NOT StopButton THEN
    step := 1;
    CycleComplete := FALSE;
END_IF;

IF step = 1 AND Zone1Moisture >= 30.0 THEN
    step := 2;
END_IF;
IF step = 2 AND Zone2Moisture >= 30.0 THEN
    step := 3;
END_IF;
IF step = 3 AND Zone3Moisture >= 30.0 THEN
    step := 4;
END_IF;
IF (zone1Timer.Q OR zone2Timer.Q OR zone3Timer.Q) THEN
    step := step + 1;
END_IF;
IF step = 4 THEN
    step := 0;
    CycleComplete := TRUE;
END_IF;

Zone1Valve := (step = 1) AND (Zone1Moisture < 30.0) AND NOT StopButton;
Zone2Valve := (step = 2) AND (Zone2Moisture < 30.0) AND NOT StopButton;
Zone3Valve := (step = 3) AND (Zone3Moisture < 30.0) AND NOT StopButton;
Pump := Zone1Valve OR Zone2Valve OR Zone3Valve;
prevStart := StartButton;
""",
    },
    {
        "id": "C09",
        "pou": "FB_C09",
        "title": "Conveyor Zone Accumulation",
        "difficulty": "hard",
        "axis": "sorting_filtering",
        "tags": ["accumulation", "handshake", "jam_detection", "timer", "state_machine"],
        "rationale": "Zone accumulation is a core material-handling function: parts must queue without collision, and a blocked zone must raise a jam alarm instead of stalling silently.",
        "requirements": """A three-zone conveyor moves parts downstream. `Zone1Sensor`, `Zone2Sensor` and `Zone3Sensor` indicate a part in each zone. A zone motor runs only when its zone has a part and the downstream zone is free. Zone 3 additionally requires `ReleaseButton` to discharge.

`Zone1Full` means zone 1 and zone 2 both contain a part; `Zone2Full` means zones 2 and 3 both contain a part; `Zone3Full` means zone 3 has a part and `ReleaseButton` is FALSE. If a zone has a part but its motor cannot run for more than 5 s, latch `JamAlarm`, switch all motors OFF and require `ResetButton` to clear the alarm.""",
        "interface": [
            ("RunSwitch", "input", "BOOL", "Enables the conveyor line"),
            ("Zone1Sensor", "input", "BOOL", "Part in zone 1"),
            ("Zone2Sensor", "input", "BOOL", "Part in zone 2"),
            ("Zone3Sensor", "input", "BOOL", "Part in zone 3"),
            ("ReleaseButton", "input", "BOOL", "Discharge zone 3"),
            ("ResetButton", "input", "BOOL", "Clears the jam alarm"),
            ("Zone1Motor", "output", "BOOL", "Zone 1 motor"),
            ("Zone2Motor", "output", "BOOL", "Zone 2 motor"),
            ("Zone3Motor", "output", "BOOL", "Zone 3 motor"),
            ("Zone1Full", "output", "BOOL", "Zone 1 blocked by zone 2"),
            ("Zone2Full", "output", "BOOL", "Zone 2 blocked by zone 3"),
            ("Zone3Full", "output", "BOOL", "Zone 3 waiting for release"),
            ("JamAlarm", "output", "BOOL", "Jam latched"),
        ],
        "atoms": [
            ("RunSwitch", "input", "RunSwitch", "Line enabled"),
            ("Zone1Sensor", "input", "Zone1Sensor", "Part in zone 1"),
            ("Zone2Sensor", "input", "Zone2Sensor", "Part in zone 2"),
            ("Zone3Sensor", "input", "Zone3Sensor", "Part in zone 3"),
            ("Zone1Motor", "output", "Zone1Motor", "Zone 1 motor"),
            ("Zone2Motor", "output", "Zone2Motor", "Zone 2 motor"),
            ("Zone3Motor", "output", "Zone3Motor", "Zone 3 motor"),
            ("Zone1Full", "output", "Zone1Full", "Zone 1 blocked"),
            ("JamAlarm", "output", "JamAlarm", "Jam latched"),
        ],
        "specs": [
            ("P1", "Zone 1 moves into a free zone 2", "G((Zone1Sensor ∧ ¬Zone2Sensor ∧ RunSwitch) → Zone1Motor)", "A part advances only when the downstream zone is free."),
            ("P2", "Zone 1 full condition", "G((Zone1Sensor ∧ Zone2Sensor) → Zone1Full)", "Two consecutive parts block zone 1."),
            ("P3", "Jam stops all motors", "G(JamAlarm → ¬(Zone1Motor ∨ Zone2Motor ∨ Zone3Motor))", "A jam must remove all drive commands."),
        ],
        "cases": [
            {
                "id": "TC01",
                "name": "normal accumulation",
                "coverage": "zone 1 moves, zone 1 full, zone 2 moves",
                "initial_state": "line enabled, empty",
                "steps": [
                    step(0, {"RunSwitch": 1, "Zone1Sensor": 1, "Zone2Sensor": 0, "Zone3Sensor": 0, "ReleaseButton": 0, "ResetButton": 1}, {"Zone1Motor": 1, "Zone2Motor": 0, "Zone1Full": 0, "JamAlarm": 0}, "zone 1 moves"),
                    step(1, {"ResetButton": 0, "Zone2Sensor": 1}, {"Zone1Motor": 0, "Zone1Full": 1, "Zone2Motor": 1, "Zone2Full": 0}, "zone 1 full, zone 2 moves"),
                    step(2, {"Zone3Sensor": 1}, {"Zone2Motor": 0, "Zone2Full": 1, "Zone3Motor": 0, "Zone3Full": 1}, "zone 2 full"),
                ],
            },
            {
                "id": "TC02",
                "name": "jam detection and reset",
                "coverage": "blocked zone 1 for 5 s, jam alarm, all motors off, reset",
                "initial_state": "line enabled",
                "steps": [
                    step(0, {"RunSwitch": 1, "Zone1Sensor": 1, "Zone2Sensor": 1, "Zone3Sensor": 0, "ReleaseButton": 0, "ResetButton": 0}, {"Zone1Full": 1, "JamAlarm": 1, "Zone1Motor": 0, "Zone2Motor": 0}, "zone 1 blocked, jam after 5 s", hold_ms=5100),
                    step(1, {"ResetButton": 1, "Zone1Sensor": 0, "Zone2Sensor": 0}, {"JamAlarm": 0, "Zone1Motor": 0, "Zone2Motor": 0}, "reset and clear sensors"),
                    step(2, {"ResetButton": 0, "Zone1Sensor": 1}, {"Zone1Motor": 1, "JamAlarm": 0}, "line restarts"),
                ],
            },
            {
                "id": "TC03",
                "name": "release zone 3",
                "coverage": "release button runs zone 3, blocked zone 3 jams",
                "initial_state": "line enabled",
                "steps": [
                    step(0, {"RunSwitch": 1, "Zone3Sensor": 1, "ReleaseButton": 1}, {"Zone3Motor": 1, "Zone3Full": 0, "JamAlarm": 0}, "release runs zone 3"),
                    step(1, {"ReleaseButton": 0}, {"Zone3Motor": 0, "Zone3Full": 1, "JamAlarm": 1}, "zone 3 blocked, jam after 5 s", hold_ms=5100),
                ],
            },
        ],
        "st": """FUNCTION_BLOCK FB_C09
VAR_INPUT
    RunSwitch : BOOL;
    Zone1Sensor : BOOL;
    Zone2Sensor : BOOL;
    Zone3Sensor : BOOL;
    ReleaseButton : BOOL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    Zone1Motor : BOOL;
    Zone2Motor : BOOL;
    Zone3Motor : BOOL;
    Zone1Full : BOOL;
    Zone2Full : BOOL;
    Zone3Full : BOOL;
    JamAlarm : BOOL;
END_VAR
VAR
    z1Timer : TON;
    z2Timer : TON;
    z3Timer : TON;
END_VAR

IF ResetButton THEN
    JamAlarm := FALSE;
END_IF;

Zone3Motor := RunSwitch AND Zone3Sensor AND ReleaseButton;
Zone2Motor := RunSwitch AND Zone2Sensor AND NOT Zone3Sensor;
Zone1Motor := RunSwitch AND Zone1Sensor AND NOT Zone2Sensor;

Zone1Full := Zone1Sensor AND Zone2Sensor;
Zone2Full := Zone2Sensor AND Zone3Sensor;
Zone3Full := Zone3Sensor AND NOT ReleaseButton;

z1Timer(IN := RunSwitch AND Zone1Sensor AND NOT Zone1Motor, PT := T#5S);
z2Timer(IN := RunSwitch AND Zone2Sensor AND NOT Zone2Motor, PT := T#5S);
z3Timer(IN := RunSwitch AND Zone3Sensor AND NOT Zone3Motor, PT := T#5S);

IF z1Timer.Q OR z2Timer.Q OR z3Timer.Q THEN
    JamAlarm := TRUE;
END_IF;

IF JamAlarm THEN
    Zone1Motor := FALSE;
    Zone2Motor := FALSE;
    Zone3Motor := FALSE;
END_IF;
""",
    },
    {
        "id": "C10",
        "pou": "FB_C10",
        "title": "Boiler Purge and Ignition Sequence",
        "difficulty": "hard",
        "axis": "safety_logic",
        "tags": ["safety_sequence", "timer", "flame_proving", "lockout", "state_machine"],
        "rationale": "Burner start-up is safety-critical: a purge must precede ignition, flame must be proven within a fixed window, and failure must latch a lockout.",
        "requirements": """A burner start is a supervised sequence. A rising edge of `StartButton` starts a 3 s purge with `PurgeFan`. After the purge, `Igniter` runs for 2 s. If `FlameSensor` becomes TRUE during ignition, open `FuelValve`, set `FlameOn` and turn the igniter OFF. If no flame is proven within 2 s, latch `Lockout` and stop the sequence.

While firing, loss of flame latches `Lockout` and closes `FuelValve`. `StopButton` stops the burner without lockout. `EmergencyStop` stops the burner and latches `Fault`. `ResetButton` clears `Lockout` and `Fault` only when `StartButton` and `FlameSensor` are FALSE. `FuelValve` requires `FlameOn`; `Igniter` and `FuelValve` must never be TRUE together.""",
        "interface": [
            ("StartButton", "input", "BOOL", "Burner start command"),
            ("StopButton", "input", "BOOL", "Normal stop"),
            ("EmergencyStop", "input", "BOOL", "Emergency stop"),
            ("FlameSensor", "input", "BOOL", "Flame proven"),
            ("ResetButton", "input", "BOOL", "Clears lockout and fault"),
            ("PurgeFan", "output", "BOOL", "Purge fan"),
            ("Igniter", "output", "BOOL", "Ignition transformer"),
            ("FuelValve", "output", "BOOL", "Fuel valve"),
            ("FlameOn", "output", "BOOL", "Flame established"),
            ("Lockout", "output", "BOOL", "Ignition lockout latched"),
            ("Fault", "output", "BOOL", "Emergency fault latched"),
        ],
        "atoms": [
            ("StartButton", "input", "StartButton", "Start command"),
            ("StopButton", "input", "StopButton", "Stop command"),
            ("EmergencyStop", "input", "EmergencyStop", "Emergency stop"),
            ("FlameSensor", "input", "FlameSensor", "Flame proven"),
            ("PurgeFan", "output", "PurgeFan", "Purge fan"),
            ("Igniter", "output", "Igniter", "Igniter"),
            ("FuelValve", "output", "FuelValve", "Fuel valve"),
            ("FlameOn", "output", "FlameOn", "Flame established"),
            ("Lockout", "output", "Lockout", "Lockout latched"),
            ("Fault", "output", "Fault", "Fault latched"),
        ],
        "specs": [
            ("P1", "Lockout removes all combustion outputs", "G(Lockout → ¬(PurgeFan ∨ Igniter ∨ FuelValve))", "A lockout must de-energize the fan, igniter and fuel valve."),
            ("P2", "Fuel requires proven flame", "G(FuelValve → FlameOn)", "Fuel must never be admitted without a proven flame."),
            ("P3", "Failed ignition locks out", "G((Igniter ∧ ¬FlameSensor) → F Lockout)", "Ignition that does not prove flame eventually latches lockout."),
        ],
        "cases": [
            {
                "id": "TC01",
                "name": "purge, ignition and normal stop",
                "coverage": "3 s purge, 2 s ignition, flame proven, stop",
                "initial_state": "burner off",
                "steps": [
                    step(0, {"StartButton": 0, "StopButton": 0, "EmergencyStop": 0, "FlameSensor": 0, "ResetButton": 1}, {"PurgeFan": 0, "Igniter": 0, "FuelValve": 0, "Lockout": 0, "Fault": 0}, "reset"),
                    step(1, {"ResetButton": 0, "StartButton": 1}, {"PurgeFan": 1, "Igniter": 0, "FuelValve": 0}, "purge starts"),
                    step(2, {"StartButton": 0}, {"PurgeFan": 0, "Igniter": 1, "FuelValve": 0}, "ignition after purge", hold_ms=3100),
                    step(3, {"FlameSensor": 1}, {"Igniter": 0, "FuelValve": 1, "FlameOn": 1, "Lockout": 0}, "flame proven"),
                    step(4, {"StopButton": 1}, {"PurgeFan": 0, "Igniter": 0, "FuelValve": 0, "FlameOn": 0}, "normal stop"),
                ],
            },
            {
                "id": "TC02",
                "name": "failed ignition lockout",
                "coverage": "purge, ignition window expires, lockout, reset",
                "initial_state": "burner off",
                "steps": [
                    step(0, {"StartButton": 1, "FlameSensor": 0}, {"PurgeFan": 1}, "purge"),
                    step(1, {"StartButton": 0}, {"Igniter": 1, "PurgeFan": 0}, "ignition", hold_ms=3100),
                    step(2, {}, {"Igniter": 0, "FuelValve": 0, "Lockout": 1}, "no flame, lockout", hold_ms=2100),
                    step(3, {"ResetButton": 1}, {"Lockout": 0, "Fault": 0}, "reset lockout"),
                ],
            },
            {
                "id": "TC03",
                "name": "emergency stop latch",
                "coverage": "emergency during purge, fault latch, reset",
                "initial_state": "burner off",
                "steps": [
                    step(0, {"StartButton": 1}, {"PurgeFan": 1, "Fault": 0}, "purge"),
                    step(1, {"StartButton": 0, "EmergencyStop": 1}, {"PurgeFan": 0, "Fault": 1}, "emergency stop"),
                    step(2, {"EmergencyStop": 0}, {"PurgeFan": 0, "Fault": 1}, "fault latched"),
                    step(3, {"ResetButton": 1}, {"Fault": 0, "Lockout": 0}, "reset"),
                ],
            },
        ],
        "st": """FUNCTION_BLOCK FB_C10
VAR_INPUT
    StartButton : BOOL;
    StopButton : BOOL;
    EmergencyStop : BOOL;
    FlameSensor : BOOL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    PurgeFan : BOOL;
    Igniter : BOOL;
    FuelValve : BOOL;
    FlameOn : BOOL;
    Lockout : BOOL;
    Fault : BOOL;
END_VAR
VAR
    step : INT;
    prevStart : BOOL;
    startEdge : BOOL;
    purgeTimer : TON;
    igniteTimer : TON;
END_VAR

startEdge := StartButton AND NOT prevStart;
purgeTimer(IN := (step = 1), PT := T#3S);
igniteTimer(IN := (step = 2), PT := T#2S);

IF EmergencyStop THEN
    Fault := TRUE;
    step := 0;
END_IF;
IF StopButton THEN
    step := 0;
END_IF;
IF ResetButton AND NOT StartButton AND NOT FlameSensor THEN
    Lockout := FALSE;
    Fault := FALSE;
END_IF;
IF startEdge AND NOT Lockout AND NOT Fault AND NOT EmergencyStop THEN
    step := 1;
END_IF;

IF step = 1 AND purgeTimer.Q THEN
    step := 2;
END_IF;
IF step = 2 THEN
    IF FlameSensor THEN
        step := 3;
    ELSIF igniteTimer.Q THEN
        Lockout := TRUE;
        step := 0;
    END_IF;
END_IF;
IF step = 3 AND NOT FlameSensor THEN
    Lockout := TRUE;
    step := 0;
END_IF;

FlameOn := (step = 3) AND FlameSensor;
PurgeFan := (step = 1) AND NOT EmergencyStop AND NOT Fault;
Igniter := (step = 2) AND NOT EmergencyStop AND NOT Fault;
FuelValve := (step = 3) AND FlameOn AND NOT EmergencyStop AND NOT StopButton AND NOT Fault;
prevStart := StartButton;
""",
    },
    {
        "id": "C11",
        "pou": "FB_C11",
        "title": "Palletizer Layer Counting",
        "difficulty": "hard",
        "axis": "sorting_filtering",
        "tags": ["counter", "batching", "timer", "sorting", "pallet"],
        "rationale": "Palletizing combines product counting, layer formation and a full-pallet handshake; it is a realistic batching and filtering problem.",
        "requirements": """A palletizer receives boxes on a conveyor. A rising edge of `BoxPresent` while `RunSwitch` is TRUE and the pallet is not full counts one box. Every 3 boxes form a layer: increment `LayerCount`, pulse `LayerPush` for 1 s and reset the box count. When `LayerCount` reaches 2, set `PalletFull` and stop the conveyor. `ResetButton` clears the box count, layer count and `PalletFull`. The conveyor must stop while `LayerPush` is active.""",
        "interface": [
            ("RunSwitch", "input", "BOOL", "Enables the conveyor"),
            ("BoxPresent", "input", "BOOL", "Box at the palletizer infeed"),
            ("ResetButton", "input", "BOOL", "Clears counts and full-pallet state"),
            ("ConveyorMotor", "output", "BOOL", "Conveyor drive"),
            ("LayerPush", "output", "BOOL", "Layer pusher"),
            ("BoxCount", "output", "INT", "Boxes in the current layer"),
            ("LayerCount", "output", "INT", "Completed layers"),
            ("PalletFull", "output", "BOOL", "Pallet complete"),
        ],
        "atoms": [
            ("RunSwitch", "input", "RunSwitch", "Conveyor enabled"),
            ("BoxPresent", "input", "BoxPresent", "Box present"),
            ("ConveyorMotor", "output", "ConveyorMotor", "Conveyor running"),
            ("LayerPush", "output", "LayerPush", "Layer pusher active"),
            ("BoxCount", "output", "BoxCount", "Boxes in current layer"),
            ("LayerCount", "output", "LayerCount", "Completed layers"),
            ("PalletFull", "output", "PalletFull", "Pallet complete"),
            ("LayerComplete", "internal", "layerTrigger", "Third box of a layer detected"),
        ],
        "specs": [
            ("P1", "Layer completion pushes", "G(LayerComplete → LayerPush)", "The third box triggers the layer pusher."),
            ("P2", "Full pallet stops conveyor", "G(PalletFull → ¬ConveyorMotor)", "A full pallet must stop the infeed."),
            ("P3", "Push pulse ends", "G((LayerPush ∧ ¬PalletFull) → F ¬LayerPush)", "The layer pusher retracts after its 1 s pulse."),
        ],
        "cases": [
            {
                "id": "TC01",
                "name": "two layers fill a pallet",
                "coverage": "three boxes per layer, layer push pulse, full pallet, reset",
                "initial_state": "counts zero",
                "steps": [
                    step(0, {"RunSwitch": 1, "BoxPresent": 0, "ResetButton": 1}, {"BoxCount": 0, "LayerCount": 0, "ConveyorMotor": 1, "PalletFull": 0}, "reset"),
                    step(1, {"ResetButton": 0, "BoxPresent": 1}, {"BoxCount": 1, "ConveyorMotor": 1}, "box 1"),
                    step(2, {"BoxPresent": 0}, {"BoxCount": 1}, "gap"),
                    step(3, {"BoxPresent": 1}, {"BoxCount": 2}, "box 2"),
                    step(4, {"BoxPresent": 0}, {"BoxCount": 2}, "gap"),
                    step(5, {"BoxPresent": 1}, {"BoxCount": 0, "LayerCount": 1, "LayerPush": 1, "ConveyorMotor": 0}, "layer 1 push"),
                    step(6, {"BoxPresent": 0}, {"LayerPush": 0, "ConveyorMotor": 1}, "push retracts", hold_ms=1100),
                    step(7, {"BoxPresent": 1}, {"BoxCount": 1}, "box 4"),
                    step(8, {"BoxPresent": 0}, {"BoxCount": 1}, "gap"),
                    step(9, {"BoxPresent": 1}, {"BoxCount": 2}, "box 5"),
                    step(10, {"BoxPresent": 0}, {"BoxCount": 2}, "gap"),
                    step(11, {"BoxPresent": 1}, {"BoxCount": 0, "LayerCount": 2, "LayerPush": 1, "PalletFull": 1, "ConveyorMotor": 0}, "layer 2 fills pallet"),
                    step(12, {"BoxPresent": 0}, {"LayerPush": 0, "ConveyorMotor": 0, "PalletFull": 1}, "push retracts, pallet remains full", hold_ms=1100),
                    step(13, {"ResetButton": 1}, {"BoxCount": 0, "LayerCount": 0, "PalletFull": 0, "ConveyorMotor": 1}, "reset pallet"),
                ],
            },
        ],
        "st": """FUNCTION_BLOCK FB_C11
VAR_INPUT
    RunSwitch : BOOL;
    BoxPresent : BOOL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    ConveyorMotor : BOOL;
    LayerPush : BOOL;
    BoxCount : INT;
    LayerCount : INT;
    PalletFull : BOOL;
END_VAR
VAR
    prevBox : BOOL;
    partEdge : BOOL;
    layerTrigger : BOOL;
    layerTimer : TOF;
END_VAR

partEdge := BoxPresent AND NOT prevBox;
layerTrigger := FALSE;

IF ResetButton THEN
    BoxCount := 0;
    LayerCount := 0;
    PalletFull := FALSE;
END_IF;

IF partEdge AND RunSwitch AND NOT PalletFull THEN
    BoxCount := BoxCount + 1;
END_IF;
IF BoxCount >= 3 THEN
    BoxCount := 0;
    LayerCount := LayerCount + 1;
    layerTrigger := TRUE;
END_IF;

layerTimer(IN := layerTrigger, PT := T#1S);
LayerPush := layerTimer.Q;

IF LayerCount >= 2 THEN
    PalletFull := TRUE;
END_IF;

ConveyorMotor := RunSwitch AND NOT PalletFull AND NOT LayerPush;
prevBox := BoxPresent;
""",
    },
    {
        "id": "C12",
        "pou": "FB_C12",
        "title": "Safety Light Curtain Muting",
        "difficulty": "hard",
        "axis": "safety_logic",
        "tags": ["safety_logic", "muting", "timer", "edge_detection", "fault_latch"],
        "rationale": "Muting lets a pallet pass through a light curtain without tripping the safety stop, but only when two sensors confirm the correct sequence; a wrong sequence must alarm.",
        "requirements": """A conveyor is protected by `LightCurtain` (TRUE means blocked). If the curtain is blocked while muting is not active, latch `SafetyStop` and stop the conveyor. `ResetButton` clears `SafetyStop` and `Alarm` only when `LightCurtain` is FALSE.

Muting requires a valid sequence: `MutingSensor1` must be activated first, then `MutingSensor2` within 2 s. A valid sequence activates `MutingActive` while both sensors remain TRUE. If `MutingSensor2` is activated without the sequence, or if the 2 s window expires, latch `Alarm`. The conveyor may run with the curtain blocked only while `MutingActive` is TRUE. `Alarm` also stops the conveyor.""",
        "interface": [
            ("RunSwitch", "input", "BOOL", "Enables the conveyor"),
            ("LightCurtain", "input", "BOOL", "Light curtain blocked"),
            ("MutingSensor1", "input", "BOOL", "First muting sensor"),
            ("MutingSensor2", "input", "BOOL", "Second muting sensor"),
            ("ResetButton", "input", "BOOL", "Clears safety stop and alarm"),
            ("ConveyorMotor", "output", "BOOL", "Conveyor drive"),
            ("MutingActive", "output", "BOOL", "Muting is active"),
            ("SafetyStop", "output", "BOOL", "Safety stop latched"),
            ("Alarm", "output", "BOOL", "Muting alarm latched"),
        ],
        "atoms": [
            ("RunSwitch", "input", "RunSwitch", "Conveyor enabled"),
            ("LightCurtain", "input", "LightCurtain", "Curtain blocked"),
            ("MutingSensor1", "input", "MutingSensor1", "Sensor 1 active"),
            ("MutingSensor2", "input", "MutingSensor2", "Sensor 2 active"),
            ("ConveyorMotor", "output", "ConveyorMotor", "Conveyor running"),
            ("MutingActive", "output", "MutingActive", "Muting active"),
            ("SafetyStop", "output", "SafetyStop", "Safety stop latched"),
            ("Alarm", "output", "Alarm", "Alarm latched"),
        ],
        "specs": [
            ("P1", "Curtain stops the conveyor", "G((LightCurtain ∧ ¬MutingActive) → SafetyStop)", "A blocked curtain without muting must latch a safety stop."),
            ("P2", "Safety stop stops the conveyor", "G(SafetyStop → ¬ConveyorMotor)", "The conveyor must not run while the safety stop is latched."),
            ("P3", "Valid sequence activates muting", "G((MutingSensor1 ∧ X MutingSensor2) → F MutingActive)", "The correct two-sensor order eventually enables muting."),
        ],
        "cases": [
            {
                "id": "TC01",
                "name": "curtain safety stop and reset",
                "coverage": "curtain blocked, safety stop latch, reset when clear",
                "initial_state": "conveyor enabled, curtain clear",
                "steps": [
                    step(0, {"RunSwitch": 1, "LightCurtain": 0, "MutingSensor1": 0, "MutingSensor2": 0, "ResetButton": 1}, {"ConveyorMotor": 1, "SafetyStop": 0, "Alarm": 0, "MutingActive": 0}, "reset"),
                    step(1, {"ResetButton": 0, "LightCurtain": 1}, {"ConveyorMotor": 0, "SafetyStop": 1, "MutingActive": 0}, "curtain blocks"),
                    step(2, {"LightCurtain": 0}, {"ConveyorMotor": 0, "SafetyStop": 1}, "stop remains latched"),
                    step(3, {"ResetButton": 1}, {"ConveyorMotor": 1, "SafetyStop": 0}, "reset while clear"),
                ],
            },
            {
                "id": "TC02",
                "name": "valid muting sequence",
                "coverage": "sensor 1 then sensor 2, curtain blocked, conveyor runs",
                "initial_state": "conveyor enabled, curtain clear",
                "steps": [
                    step(0, {"RunSwitch": 1, "MutingSensor1": 1, "MutingSensor2": 0, "LightCurtain": 0}, {"MutingActive": 0, "ConveyorMotor": 1}, "sensor 1 armed"),
                    step(1, {"MutingSensor2": 1, "LightCurtain": 1}, {"MutingActive": 1, "ConveyorMotor": 1, "SafetyStop": 0, "Alarm": 0}, "valid muting"),
                    step(2, {"MutingSensor1": 1, "MutingSensor2": 1, "LightCurtain": 1}, {"MutingActive": 1, "ConveyorMotor": 1}, "muting holds"),
                    step(3, {"MutingSensor1": 0, "MutingSensor2": 0, "LightCurtain": 1}, {"MutingActive": 0, "ConveyorMotor": 0, "SafetyStop": 1}, "muting ends, curtain still blocked"),
                    step(4, {"LightCurtain": 0, "ResetButton": 1}, {"SafetyStop": 0, "ConveyorMotor": 1}, "reset"),
                ],
            },
            {
                "id": "TC03",
                "name": "wrong sequence and muting timeout",
                "coverage": "sensor 2 first, alarm; sensor 1 alone 2 s, alarm",
                "initial_state": "conveyor enabled, curtain clear",
                "steps": [
                    step(0, {"RunSwitch": 1, "MutingSensor1": 0, "MutingSensor2": 1, "LightCurtain": 0}, {"Alarm": 1, "ConveyorMotor": 0, "MutingActive": 0}, "sensor 2 without sensor 1"),
                    step(1, {"ResetButton": 1, "MutingSensor2": 0}, {"Alarm": 0, "ConveyorMotor": 1}, "reset alarm"),
                    step(2, {"ResetButton": 0, "MutingSensor1": 1}, {"Alarm": 1, "ConveyorMotor": 0}, "sensor 1 alone times out", hold_ms=2100),
                    step(3, {"MutingSensor1": 0, "ResetButton": 1}, {"Alarm": 0, "ConveyorMotor": 1}, "reset timeout"),
                ],
            },
        ],
        "st": """FUNCTION_BLOCK FB_C12
VAR_INPUT
    RunSwitch : BOOL;
    LightCurtain : BOOL;
    MutingSensor1 : BOOL;
    MutingSensor2 : BOOL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    ConveyorMotor : BOOL;
    MutingActive : BOOL;
    SafetyStop : BOOL;
    Alarm : BOOL;
END_VAR
VAR
    prevM1 : BOOL;
    prevM2 : BOOL;
    mutingArmed : BOOL;
    mutingActiveState : BOOL;
    muteWindow : TON;
END_VAR

muteWindow(IN := mutingArmed, PT := T#2S);

IF ResetButton AND NOT LightCurtain THEN
    SafetyStop := FALSE;
    Alarm := FALSE;
END_IF;

IF MutingSensor1 AND NOT prevM1 THEN
    mutingArmed := TRUE;
END_IF;

IF MutingSensor2 AND NOT prevM2 THEN
    IF mutingArmed AND NOT muteWindow.Q THEN
        mutingActiveState := TRUE;
    ELSE
        Alarm := TRUE;
    END_IF;
    mutingArmed := FALSE;
END_IF;

IF muteWindow.Q THEN
    Alarm := TRUE;
    mutingArmed := FALSE;
END_IF;

IF NOT (MutingSensor1 AND MutingSensor2) THEN
    mutingActiveState := FALSE;
END_IF;

IF LightCurtain AND NOT mutingActiveState THEN
    SafetyStop := TRUE;
END_IF;

ConveyorMotor := RunSwitch AND NOT SafetyStop AND (NOT LightCurtain OR mutingActiveState) AND NOT Alarm;
MutingActive := mutingActiveState;
prevM1 := MutingSensor1;
prevM2 := MutingSensor2;
""",
    },
]
