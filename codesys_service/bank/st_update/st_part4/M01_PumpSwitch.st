TYPE ST_Pump :
STRUCT
    priority  : INT;
    selection : BOOL;
    RunComd   : BOOL;
END_STRUCT
END_TYPE

(* Q07 Multi-Pump Switching Control System - reference solution *)
FUNCTION_BLOCK M01_PumpSwitch
VAR_INPUT
    mode  : BOOL;
    start : BOOL;
    stop  : BOOL;
END_VAR
VAR_IN_OUT
    pumpGroup : ARRAY[1..5] OF ST_Pump;
END_VAR
VAR
    i, j, best, bestIdx, picked : INT;
    chosen : ARRAY[1..5] OF BOOL;
    running : BOOL;
END_VAR

IF stop THEN
    FOR i := 1 TO 5 DO
        pumpGroup[i].RunComd := FALSE;
    END_FOR;
    running := FALSE;
ELSIF start THEN
    running := TRUE;
END_IF;

IF running THEN
    IF NOT mode THEN
        (* manual: run exactly the selected pumps *)
        FOR i := 1 TO 5 DO
            pumpGroup[i].RunComd := pumpGroup[i].selection;
        END_FOR;
    ELSE
        (* automatic: three highest priorities run, two stand by *)
        FOR i := 1 TO 5 DO
            chosen[i] := FALSE;
        END_FOR;
        FOR picked := 1 TO 3 DO
            bestIdx := 0;
            FOR j := 1 TO 5 DO
                IF NOT chosen[j] THEN
                    IF bestIdx = 0 THEN
                        bestIdx := j;
                        best := pumpGroup[j].priority;
                    ELSIF pumpGroup[j].priority > best THEN
                        bestIdx := j;
                        best := pumpGroup[j].priority;
                    END_IF;
                END_IF;
            END_FOR;
            IF bestIdx > 0 THEN
                chosen[bestIdx] := TRUE;
            END_IF;
        END_FOR;
        FOR i := 1 TO 5 DO
            pumpGroup[i].RunComd := chosen[i];
        END_FOR;
    END_IF;
END_IF;
