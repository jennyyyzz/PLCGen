FUNCTION_BLOCK M06_SlabThick
VAR_INPUT
    THICKNESS_FAULT : BOOL;
    THICKNESS_SIGNAL_VALID : BOOL;
    CUTTING_RUN : BOOL;
    FaultTimestamp : DINT;
    CycleTime : TIME;
END_VAR
VAR_OUTPUT
    THICKNESS_ALARM : BOOL;
    Slab_Fault_Counter : UINT;
    Slab_Runtime_Accumulator : LTIME;
    Slab_Fault_History : ARRAY[0..4] OF DINT;
END_VAR
VAR
    holdTimer : TOF;
    prevFault : BOOL;
END_VAR

IF THICKNESS_SIGNAL_VALID THEN
    (* alarm with minimum 500ms hold (TOF) while fault persists *)
    holdTimer(IN := THICKNESS_FAULT, PT := T#500MS);
    THICKNESS_ALARM := THICKNESS_FAULT OR holdTimer.Q;

    (* fault bookkeeping on rising edge of a valid fault *)
    IF THICKNESS_FAULT AND NOT prevFault THEN
        Slab_Fault_Counter := Slab_Fault_Counter + 1;
        Slab_Fault_History[4] := Slab_Fault_History[3];
        Slab_Fault_History[3] := Slab_Fault_History[2];
        Slab_Fault_History[2] := Slab_Fault_History[1];
        Slab_Fault_History[1] := Slab_Fault_History[0];
        Slab_Fault_History[0] := FaultTimestamp;
    END_IF;

    (* normal-cutting runtime accumulation *)
    IF CUTTING_RUN AND NOT THICKNESS_FAULT THEN
        Slab_Runtime_Accumulator := Slab_Runtime_Accumulator + TIME_TO_LTIME(CycleTime);
    END_IF;
ELSE
    (* signal invalid: alarm off, holding state cleared *)
    THICKNESS_ALARM := FALSE;
    holdTimer(IN := FALSE, PT := T#500MS);
END_IF;

prevFault := THICKNESS_FAULT;
