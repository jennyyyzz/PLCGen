FUNCTION_BLOCK FB_C03
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
