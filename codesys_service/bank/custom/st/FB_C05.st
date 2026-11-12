FUNCTION_BLOCK FB_C05
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
