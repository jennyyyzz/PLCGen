(* Q10 Temperature Logic Control - reference solution *)
FUNCTION_BLOCK FB_Q10
VAR_INPUT
    TemperatureSensorInput : REAL;
    SetTemperature         : REAL;
END_VAR
VAR_OUTPUT
    CurrentTemperature : REAL;
    SetTempDisplay     : REAL;
    HeaterStatus       : BOOL;
    OverheatProtection : BOOL;
    HeaterOutput       : BOOL;
END_VAR
VAR
    runTimer  : TON;
    coolTimer : TON;
    sensorFault : BOOL;
END_VAR

CurrentTemperature := TemperatureSensorInput;
SetTempDisplay := SetTemperature;
sensorFault := FALSE;

runTimer(IN := HeaterOutput, PT := T#5S);
IF runTimer.Q THEN
    OverheatProtection := TRUE;
END_IF;

coolTimer(IN := OverheatProtection, PT := T#3S);
IF coolTimer.Q THEN
    OverheatProtection := FALSE;
END_IF;

IF sensorFault OR OverheatProtection THEN
    HeaterOutput := FALSE;
ELSIF TemperatureSensorInput < SetTemperature THEN
    HeaterOutput := TRUE;
ELSE
    HeaterOutput := FALSE;
END_IF;

HeaterStatus := HeaterOutput;
