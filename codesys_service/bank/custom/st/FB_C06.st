FUNCTION_BLOCK FB_C06
VAR_INPUT
    OpenButton : BOOL;
    CloseButton : BOOL;
    ObstacleSensor : BOOL;
    DoorOpenLimit : BOOL;
    DoorClosedLimit : BOOL;
    ResetButton : BOOL;
END_VAR
VAR_OUTPUT
    DoorMotorOpen : BOOL;
    DoorMotorClose : BOOL;
    DoorOpen : BOOL;
    DoorClosed : BOOL;
    WarningBuzzer : BOOL;
    Fault : BOOL;
END_VAR
VAR
    opening : BOOL;
    closing : BOOL;
    autoTimer : TON;
END_VAR

IF DoorOpenLimit AND DoorClosedLimit THEN
    Fault := TRUE;
    opening := FALSE;
    closing := FALSE;
ELSIF ResetButton THEN
    Fault := FALSE;
END_IF;

IF NOT Fault THEN
    IF (OpenButton AND NOT DoorOpenLimit) OR (ObstacleSensor AND closing) THEN
        opening := TRUE;
        closing := FALSE;
    END_IF;

    IF CloseButton AND NOT ObstacleSensor AND NOT OpenButton THEN
        closing := TRUE;
        opening := FALSE;
    END_IF;

    autoTimer(IN := DoorOpenLimit AND NOT ObstacleSensor AND NOT OpenButton AND NOT CloseButton, PT := T#5S);
    IF autoTimer.Q AND NOT ObstacleSensor THEN
        closing := TRUE;
        opening := FALSE;
    END_IF;

    IF ObstacleSensor THEN
        opening := TRUE;
        closing := FALSE;
    END_IF;

    IF opening AND DoorOpenLimit THEN
        opening := FALSE;
    END_IF;
    IF closing AND DoorClosedLimit THEN
        closing := FALSE;
    END_IF;
ELSE
    opening := FALSE;
    closing := FALSE;
    autoTimer(IN := FALSE, PT := T#5S);
END_IF;

DoorMotorOpen := opening;
DoorMotorClose := closing;
DoorOpen := DoorOpenLimit;
DoorClosed := DoorClosedLimit;
WarningBuzzer := ObstacleSensor;
