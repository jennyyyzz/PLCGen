FUNCTION_BLOCK FB_C02
VAR_INPUT
    LeftButton : BOOL;
    RightButton : BOOL;
    PartPresent : BOOL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    PressOutput : BOOL;
    CycleComplete : BOOL;
    Fault : BOOL;
END_VAR
VAR
    leftTimer : TON;
    rightTimer : TON;
    pressWasOn : BOOL;
END_VAR

leftTimer(IN := LeftButton AND NOT RightButton, PT := T#500MS);
rightTimer(IN := RightButton AND NOT LeftButton, PT := T#500MS);

IF leftTimer.Q OR rightTimer.Q THEN
    Fault := TRUE;
END_IF;

IF ResetButton AND NOT LeftButton AND NOT RightButton THEN
    Fault := FALSE;
END_IF;

PressOutput := LeftButton AND RightButton AND PartPresent AND NOT Fault;
CycleComplete := pressWasOn AND NOT PressOutput;
pressWasOn := PressOutput;
