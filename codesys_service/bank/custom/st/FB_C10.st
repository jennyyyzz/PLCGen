FUNCTION_BLOCK FB_C10
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
