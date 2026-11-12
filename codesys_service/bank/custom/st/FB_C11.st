FUNCTION_BLOCK FB_C11
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
