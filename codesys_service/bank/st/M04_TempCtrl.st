FUNCTION_BLOCK M04_TempCtrl
VAR_INPUT
    TemperatureSensorInput : REAL;
    SetTemperature : REAL;
END_VAR
VAR_OUTPUT
    CurrentTemperature : REAL;
    SetTempDisplay : REAL;
    HeaterStatus : BOOL;
    OverheatProtection : BOOL;
    HeaterOutput : BOOL;
END_VAR
VAR
    heatTimer : TON;
    releaseTimer : TON;
    sensorFault : BOOL;
END_VAR

CurrentTemperature := TemperatureSensorInput;
SetTempDisplay := SetTemperature;

sensorFault := (TemperatureSensorInput < 0.0) OR (TemperatureSensorInput > 100.0);

IF sensorFault THEN
    HeaterOutput := FALSE;
    OverheatProtection := FALSE;
    heatTimer(IN := FALSE, PT := T#5S);
    releaseTimer(IN := FALSE, PT := T#3S);
ELSIF OverheatProtection THEN
    (* protection active: heater forced off, heat timing reset,
       lift after 3s pause *)
    HeaterOutput := FALSE;
    heatTimer(IN := FALSE, PT := T#5S);
    releaseTimer(IN := TRUE, PT := T#3S);
    IF releaseTimer.Q THEN
        OverheatProtection := FALSE;
    END_IF;
ELSE
    HeaterOutput := (TemperatureSensorInput < SetTemperature);
    heatTimer(IN := HeaterOutput, PT := T#5S);
    releaseTimer(IN := FALSE, PT := T#3S);
    IF heatTimer.Q THEN
        OverheatProtection := TRUE;
        HeaterOutput := FALSE;
    END_IF;
END_IF;

HeaterStatus := HeaterOutput;
