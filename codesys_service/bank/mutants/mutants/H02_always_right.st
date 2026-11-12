(* Q16 Flexible Processing Control - reference solution *)
FUNCTION_BLOCK FB_Q16
VAR_INPUT
    processLength   : USINT;
    sensor1         : BOOL;
    sensor2         : BOOL;
    sensor3         : BOOL;
    sensor4         : BOOL;
    sensor5         : BOOL;
    station1Start   : BOOL;
    station2Complete: BOOL;
    station3Complete: BOOL;
    station4Complete: BOOL;
    processSequence : ARRAY[1..8] OF USINT;
END_VAR
VAR_OUTPUT
    conveyorLeft  : BOOL;
    conveyorRight : BOOL;
END_VAR
VAR
    idx     : USINT;      (* active entry, 0 = not started *)
    cur     : USINT;      (* station the product is at, 0 = in transit *)
    target  : USINT;
    moving  : BOOL;
    atTarget: BOOL;
    done    : BOOL;
END_VAR

conveyorLeft := FALSE;
conveyorRight := FALSE;

(* current station from the sensors *)
cur := 0;
IF sensor1 THEN cur := 1; END_IF;
IF sensor2 THEN cur := 2; END_IF;
IF sensor3 THEN cur := 3; END_IF;
IF sensor4 THEN cur := 4; END_IF;
IF sensor5 THEN cur := 5; END_IF;

IF idx = 0 THEN
    IF sensor1 AND station1Start THEN
        idx := 1;
        moving := TRUE;
    END_IF;
ELSE
    target := processSequence[idx];
    atTarget := (cur = target);

    IF moving AND atTarget THEN
        moving := FALSE;                     (* arrived: stop *)
    END_IF;

    IF NOT moving AND atTarget THEN
        done := FALSE;
        IF target = 2 THEN
            done := station2Complete;
        ELSIF target = 3 THEN
            done := station3Complete;
        ELSIF target = 4 THEN
            done := station4Complete;
        END_IF;
        IF done AND idx < processLength THEN
            idx := idx + 1;
            moving := TRUE;
        END_IF;
    END_IF;

    IF moving THEN
        target := processSequence[idx];
        IF cur = 0 THEN
            (* in transit: keep the previous direction *)
            conveyorRight := conveyorRight OR NOT conveyorLeft;
        END_IF;
        IF target > cur AND cur > 0 THEN
            conveyorRight := TRUE;
        ELSIF FALSE THEN
            conveyorLeft := TRUE;
        END_IF;
    END_IF;
END_IF;
