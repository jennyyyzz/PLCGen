FUNCTION_BLOCK FB_C07
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
