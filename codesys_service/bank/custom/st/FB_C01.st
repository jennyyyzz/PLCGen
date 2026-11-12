FUNCTION_BLOCK FB_C01
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
