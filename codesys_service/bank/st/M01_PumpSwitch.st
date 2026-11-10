TYPE ST_Pump :
STRUCT
    priority : INT;
    selection : BOOL;
    RunComd : BOOL;
END_STRUCT
END_TYPE

FUNCTION_BLOCK M01_PumpSwitch
VAR_INPUT
    mode : BOOL;
    start : BOOL;
    stop : BOOL;
END_VAR
VAR_IN_OUT
    pumpGroup : ARRAY[1..5] OF ST_Pump;
END_VAR
VAR_OUTPUT
    runningCount : INT;
END_VAR
VAR
    i : INT;
    j : INT;
    rank : INT;
END_VAR

IF stop THEN
    FOR i := 1 TO 5 DO
        pumpGroup[i].RunComd := FALSE;
    END_FOR;
ELSIF mode THEN
    (* automatic: rank by priority, ties broken by index; top 3 run *)
    FOR i := 1 TO 5 DO
        rank := 1;
        FOR j := 1 TO 5 DO
            IF j <> i THEN
                IF (pumpGroup[j].priority > pumpGroup[i].priority)
                    OR ((pumpGroup[j].priority = pumpGroup[i].priority) AND (j < i)) THEN
                    rank := rank + 1;
                END_IF;
            END_IF;
        END_FOR;
        pumpGroup[i].RunComd := start AND (rank <= 3);
    END_FOR;
ELSE
    (* manual: selected pumps start with the start button *)
    FOR i := 1 TO 5 DO
        pumpGroup[i].RunComd := start AND pumpGroup[i].selection;
    END_FOR;
END_IF;

runningCount := 0;
FOR i := 1 TO 5 DO
    IF pumpGroup[i].RunComd THEN
        runningCount := runningCount + 1;
    END_IF;
END_FOR;
