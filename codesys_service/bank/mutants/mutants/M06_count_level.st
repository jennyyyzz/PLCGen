(* Q12 Slab Thickness Alarm and Fault History - reference solution
   Unit convention: CycleTime in ms, Slab_Runtime_Accumulator in ns (LTIME). *)
FUNCTION_BLOCK FB_Q12
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
    holdAcc  : UDINT;   (* ms *)
    accNs    : ULINT;   (* ns *)
    prevFlt  : BOOL;
    i        : INT;
END_VAR

IF NOT THICKNESS_SIGNAL_VALID THEN
    THICKNESS_ALARM := FALSE;
    holdAcc := 0;
    prevFlt := FALSE;
ELSE
    IF THICKNESS_FAULT THEN
        (* new fault: count and record *)
        Slab_Fault_Counter := Slab_Fault_Counter + 1;
        FOR i := 4 TO 1 BY -1 DO
            Slab_Fault_History[i] := Slab_Fault_History[i-1];
        END_FOR;
        Slab_Fault_History[0] := FaultTimestamp;
        THICKNESS_ALARM := TRUE;
        holdAcc := 0;
    END_IF;
    prevFlt := THICKNESS_FAULT;

    IF THICKNESS_ALARM THEN
        IF THICKNESS_FAULT THEN
            holdAcc := 0;                       (* hold while the fault persists *)
        ELSE
            holdAcc := holdAcc + TIME_TO_UDINT(CycleTime);
            IF holdAcc >= 500 THEN
                THICKNESS_ALARM := FALSE;
            END_IF;
        END_IF;
    END_IF;

    IF CUTTING_RUN AND NOT THICKNESS_FAULT THEN
        accNs := accNs + UDINT_TO_ULINT(TIME_TO_UDINT(CycleTime)) * 1000000;
        Slab_Runtime_Accumulator := ULINT_TO_LTIME(accNs);
    END_IF;
END_IF;
