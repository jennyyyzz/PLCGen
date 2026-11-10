FUNCTION_BLOCK H02_FlexProcess
VAR_INPUT
    processLength : USINT;
    sensor1 : BOOL;
    sensor2 : BOOL;
    sensor3 : BOOL;
    sensor4 : BOOL;
    sensor5 : BOOL;
    station1Start : BOOL;
    station2Complete : BOOL;
    station3Complete : BOOL;
    station4Complete : BOOL;
    processSequence : ARRAY[1..8] OF USINT;
END_VAR
VAR_OUTPUT
    conveyorLeft : BOOL;
    conveyorRight : BOOL;
END_VAR
VAR
    idx : INT := 1;      (* next sequence entry to execute *)
    cur : INT := 1;      (* current station position *)
    tgt : INT;           (* target station *)
    moving : BOOL;
    prevStart : BOOL;
    done : BOOL;
END_VAR

conveyorLeft := FALSE;
conveyorRight := FALSE;

IF (idx > processLength) OR (processLength < 1) OR (processLength > 8) THEN
    (* sequence exhausted: stay idle *)
    moving := FALSE;
    done := (idx > processLength) AND (processLength >= 1);
ELSE
    tgt := processSequence[idx];

    IF NOT moving THEN
        done := FALSE;
        IF cur = 1 THEN
            (* waiting at loading station for start *)
            IF sensor1 AND station1Start AND NOT prevStart THEN
                moving := TRUE;
            END_IF;
        ELSE
            (* waiting for completion signal of the current processing station *)
            IF (cur = 2 AND station2Complete)
                OR (cur = 3 AND station3Complete)
                OR (cur = 4 AND station4Complete) THEN
                moving := TRUE;
            END_IF;
        END_IF;
    END_IF;

    IF moving THEN
        IF tgt > cur THEN
            conveyorRight := TRUE;
        ELSIF tgt < cur THEN
            conveyorLeft := TRUE;
        END_IF;
        (* stop on arrival at the target station *)
        IF (tgt = 2 AND sensor2)
            OR (tgt = 3 AND sensor3)
            OR (tgt = 4 AND sensor4)
            OR (tgt = 5 AND sensor5) THEN
            moving := FALSE;
            conveyorLeft := FALSE;
            conveyorRight := FALSE;
            cur := tgt;
            idx := idx + 1;
        END_IF;
    END_IF;
END_IF;

prevStart := station1Start;
