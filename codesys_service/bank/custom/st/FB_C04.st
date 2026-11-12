FUNCTION_BLOCK FB_C04
VAR_INPUT
    StartButton : BOOL;
    StopButton : BOOL;
    Overload : BOOL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    MainContactor : BOOL;
    StarContactor : BOOL;
    DeltaContactor : BOOL;
    Running : BOOL;
    Fault : BOOL;
END_VAR
VAR
    prevStart : BOOL;
    startEdge : BOOL;
    starTimer : TON;
END_VAR

startEdge := StartButton AND NOT prevStart;

IF Overload THEN
    Fault := TRUE;
END_IF;
IF ResetButton AND NOT Overload THEN
    Fault := FALSE;
END_IF;

IF Fault OR StopButton THEN
    MainContactor := FALSE;
    StarContactor := FALSE;
    DeltaContactor := FALSE;
    Running := FALSE;
    starTimer(IN := FALSE, PT := T#3S);
ELSIF startEdge THEN
    MainContactor := TRUE;
    StarContactor := TRUE;
    DeltaContactor := FALSE;
    Running := TRUE;
    starTimer(IN := TRUE, PT := T#3S);
ELSE
    IF MainContactor THEN
        starTimer(IN := StarContactor, PT := T#3S);
        IF starTimer.Q THEN
            StarContactor := FALSE;
            DeltaContactor := TRUE;
        END_IF;
    END_IF;
END_IF;

prevStart := StartButton;
