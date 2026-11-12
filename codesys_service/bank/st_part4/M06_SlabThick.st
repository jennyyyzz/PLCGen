(* Q12 Slab Thickness Alarm and Fault History - reference solution
   Unit convention: CycleTime in ms, Slab_Runtime_Accumulator in ms (LTIME). *)
FUNCTION_BLOCK M06_SlabThick
VAR_INPUT
    THICKNESS_FAULT        : BOOL;
    THICKNESS_SIGNAL_VALID : BOOL;
    CUTTING_RUN            : BOOL;
    FaultTimestamp         : DINT;
    CycleTime              : TIME;
END_VAR
VAR_OUTPUT
    THICKNESS_ALARM          : BOOL;
    Slab_Fault_Counter       : UINT;
    Slab_Runtime_Accumulator : LTIME;
    Slab_Fault_History       : ARRAY[0..4] OF DINT;
END_VAR
VAR
    holdT    : TON;     (* real elapsed time, scan-clock driven *)
    accMs    : ULINT;   (* ms, per the team convention *)
    prevFlt  : BOOL;
    i        : INT;
END_VAR

IF NOT THICKNESS_SIGNAL_VALID THEN
    THICKNESS_ALARM := FALSE;
    holdT(IN := FALSE, PT := T#500MS);
    prevFlt := FALSE;
ELSE
    IF THICKNESS_FAULT AND NOT prevFlt THEN
        (* new fault: count and record *)
        Slab_Fault_Counter := Slab_Fault_Counter + 1;
        FOR i := 4 TO 1 BY -1 DO
            Slab_Fault_History[i] := Slab_Fault_History[i-1];
        END_FOR;
        Slab_Fault_History[0] := FaultTimestamp;
        THICKNESS_ALARM := TRUE;
        holdT(IN := TRUE, PT := T#500MS);
    END_IF;
    prevFlt := THICKNESS_FAULT;

    IF THICKNESS_ALARM THEN
        (* restart the 500 ms window whenever the fault is still present *)
        holdT(IN := NOT THICKNESS_FAULT, PT := T#500MS);
        IF holdT.Q THEN
            THICKNESS_ALARM := FALSE;
        END_IF;
    END_IF;

    IF CUTTING_RUN AND NOT THICKNESS_FAULT THEN
        accMs := accMs + UDINT_TO_ULINT(TIME_TO_UDINT(CycleTime));
        Slab_Runtime_Accumulator := ULINT_TO_LTIME(accMs);
    END_IF;
END_IF;
