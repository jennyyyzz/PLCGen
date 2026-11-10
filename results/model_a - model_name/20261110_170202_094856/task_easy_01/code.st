PROGRAM PLC_PRG
VAR_INPUT
    bottleSensor: BOOL;
    cleaningConfirmButton: BOOL;
    fillingConfirmButton: BOOL;
    cappingConfirmButton: BOOL;
    packingConfirmButton: BOOL;
    finishedButton: BOOL;
END_VAR
VAR_OUTPUT
    Pump_Motor: BOOL;
    Filling_Valve: BOOL;
    Capping_Machine: BOOL;
    Packing_Machine: BOOL;
    Completion_Light: BOOL;
END_VAR
VAR
    State: INT := 0;
    trBottleSensor: R_TRIG;
    trCleaningConfirm: R_TRIG;
    trFillingConfirm: R_TRIG;
    trCappingConfirm: R_TRIG;
    trPackingConfirm: R_TRIG;
    trFinished: R_TRIG;
END_VAR

trBottleSensor(CLK := bottleSensor);
trCleaningConfirm(CLK := cleaningConfirmButton);
trFillingConfirm(CLK := fillingConfirmButton);
trCappingConfirm(CLK := cappingConfirmButton);
trPackingConfirm(CLK := packingConfirmButton);
trFinished(CLK := finishedButton);

CASE State OF
    0: (* IDLE *)
        Pump_Motor := FALSE;
        Filling_Valve := FALSE;
        Capping_Machine := FALSE;
        Packing_Machine := FALSE;
        Completion_Light := FALSE;

        IF trBottleSensor.Q THEN
            State := 1;
        END_IF

    1: (* CLEANING *)
        Pump_Motor := TRUE;
        Filling_Valve := FALSE;
        Capping_Machine := FALSE;
        Packing_Machine := FALSE;
        Completion_Light := FALSE;

        IF trCleaningConfirm.Q THEN
            State := 2;
        END_IF

    2: (* FILLING *)
        Pump_Motor := FALSE;
        Filling_Valve := TRUE;
        Capping_Machine := FALSE;
        Packing_Machine := FALSE;
        Completion_Light := FALSE;

        IF trFillingConfirm.Q THEN
            State := 3;
        END_IF

    3: (* CAPPING *)
        Pump_Motor := FALSE;
        Filling_Valve := FALSE;
        Capping_Machine := TRUE;
        Packing_Machine := FALSE;
        Completion_Light := FALSE;

        IF trCappingConfirm.Q THEN
            State := 4;
        END_IF

    4: (* PACKING *)
        Pump_Motor := FALSE;
        Filling_Valve := FALSE;
        Capping_Machine := FALSE;
        Packing_Machine := TRUE;
        Completion_Light := FALSE;

        IF trPackingConfirm.Q THEN
            State := 5;
        END_IF

    5: (* COMPLETE *)
        Pump_Motor := FALSE;
        Filling_Valve := FALSE;
        Capping_Machine := FALSE;
        Packing_Machine := FALSE;
        Completion_Light := TRUE;

        IF trFinished.Q THEN
            State := 0;
        END_IF
END_CASE