FUNCTION_BLOCK FB_C09
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
