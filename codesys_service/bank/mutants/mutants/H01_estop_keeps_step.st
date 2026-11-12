FUNCTION_BLOCK H01_Proportion
VAR_INPUT
    estop : BOOL;
    opeMode : BOOL;
    valveAStart : BOOL;
    valveBStart : BOOL;
    valveCStart : BOOL;
    valveDStart : BOOL;
    mixMotorStart : BOOL;
    autoStart : BOOL;
    processMode : BOOL;
    levelSensor : INT;
    mixMotorComplete : BOOL;
END_VAR
VAR_OUTPUT
    valveARun : BOOL;
    valveBRun : BOOL;
    valveCRun : BOOL;
    valveDRun : BOOL;
    mixMotorRun : BOOL;
END_VAR
VAR
    step : INT;  (* 0=idle 1=fillA 2=fillB 3=fillC 4=mixing 5=done *)
    prevAuto : BOOL;
    prevVA : BOOL;
    prevVB : BOOL;
    prevVC : BOOL;
    prevVD : BOOL;
    prevMix : BOOL;
END_VAR

IF NOT estop THEN
    (* emergency stop: everything off, sequence aborted *)
    valveARun := FALSE;
    valveBRun := FALSE;
    valveCRun := FALSE;
    valveDRun := FALSE;
    mixMotorRun := FALSE;
    (* bug: step is kept across the e-stop *)
ELSIF NOT opeMode THEN
    (* manual mode: each button toggles its device on a rising edge *)
    IF valveAStart AND NOT prevVA THEN
        valveARun := NOT valveARun;
    END_IF;
    IF valveBStart AND NOT prevVB THEN
        valveBRun := NOT valveBRun;
    END_IF;
    IF valveCStart AND NOT prevVC THEN
        valveCRun := NOT valveCRun;
    END_IF;
    IF valveDStart AND NOT prevVD THEN
        valveDRun := NOT valveDRun;
    END_IF;
    IF mixMotorStart AND NOT prevMix THEN
        mixMotorRun := NOT mixMotorRun;
    END_IF;
    step := 0;
ELSE
    (* automatic mode state machine *)
    valveCRun := FALSE;
    mixMotorRun := FALSE;
    IF step = 0 THEN
        valveARun := FALSE;
        valveBRun := FALSE;
        valveDRun := FALSE;
        IF autoStart AND NOT prevAuto THEN
            valveARun := TRUE;
            step := 1;
        END_IF;
    ELSIF step = 1 THEN
        valveARun := TRUE;
        IF levelSensor >= 50 THEN
            valveARun := FALSE;
            valveBRun := TRUE;
            step := 2;
        END_IF;
    ELSIF step = 2 THEN
        valveBRun := TRUE;
        IF levelSensor >= 80 THEN
            valveBRun := FALSE;
            IF processMode THEN
                valveCRun := TRUE;
                step := 3;
            ELSE
                mixMotorRun := TRUE;
                step := 4;
            END_IF;
        END_IF;
    ELSIF step = 3 THEN
        valveCRun := TRUE;
        IF levelSensor >= 100 THEN
            valveCRun := FALSE;
            mixMotorRun := TRUE;
            step := 4;
        END_IF;
    ELSIF step = 4 THEN
        mixMotorRun := TRUE;
        IF mixMotorComplete THEN
            mixMotorRun := FALSE;
            valveDRun := TRUE;
            step := 5;
        END_IF;
    ELSE
        (* step 5: process finished, valve D stays open *)
        valveDRun := TRUE;
    END_IF;
END_IF;

prevAuto := autoStart;
prevVA := valveAStart;
prevVB := valveBStart;
prevVC := valveCStart;
prevVD := valveDStart;
prevMix := mixMotorStart;
