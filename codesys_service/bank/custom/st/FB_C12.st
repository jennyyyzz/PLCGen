FUNCTION_BLOCK FB_C12
VAR_INPUT
    RunSwitch : BOOL;
    LightCurtain : BOOL;
    MutingSensor1 : BOOL;
    MutingSensor2 : BOOL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    ConveyorMotor : BOOL;
    MutingActive : BOOL;
    SafetyStop : BOOL;
    Alarm : BOOL;
END_VAR
VAR
    prevM1 : BOOL;
    prevM2 : BOOL;
    mutingArmed : BOOL;
    mutingActiveState : BOOL;
    muteWindow : TON;
END_VAR

muteWindow(IN := mutingArmed, PT := T#2S);

IF ResetButton AND NOT LightCurtain THEN
    SafetyStop := FALSE;
    Alarm := FALSE;
END_IF;

IF MutingSensor1 AND NOT prevM1 THEN
    mutingArmed := TRUE;
END_IF;

IF MutingSensor2 AND NOT prevM2 THEN
    IF mutingArmed AND NOT muteWindow.Q THEN
        mutingActiveState := TRUE;
    ELSE
        Alarm := TRUE;
    END_IF;
    mutingArmed := FALSE;
END_IF;

IF muteWindow.Q THEN
    Alarm := TRUE;
    mutingArmed := FALSE;
END_IF;

IF NOT (MutingSensor1 AND MutingSensor2) THEN
    mutingActiveState := FALSE;
END_IF;

IF LightCurtain AND NOT mutingActiveState THEN
    SafetyStop := TRUE;
END_IF;

ConveyorMotor := RunSwitch AND NOT SafetyStop AND (NOT LightCurtain OR mutingActiveState) AND NOT Alarm;
MutingActive := mutingActiveState;
prevM1 := MutingSensor1;
prevM2 := MutingSensor2;
