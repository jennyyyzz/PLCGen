FUNCTION_BLOCK FB_C08
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
