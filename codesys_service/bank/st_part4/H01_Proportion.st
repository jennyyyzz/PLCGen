(* Q15 Material Proportioning Process Control - reference solution for test-case validation *)
FUNCTION_BLOCK H01_Proportion
VAR_INPUT
    estop           : BOOL;
    opeMode         : BOOL;
    valveAStart     : BOOL;
    valveBStart     : BOOL;
    valveCStart     : BOOL;
    valveDStart     : BOOL;
    mixMotorStart   : BOOL;
    autoStart       : BOOL;
    processMode     : BOOL;
    levelSensor     : INT;
    mixMotorComplete: BOOL;
END_VAR
VAR_OUTPUT
    valveARun   : BOOL;
    valveBRun   : BOOL;
    valveCRun   : BOOL;
    valveDRun   : BOOL;
    mixMotorRun : BOOL;
END_VAR
VAR
    step : INT := 0;
    pA : BOOL;
    pB : BOOL;
    pC : BOOL;
    pD : BOOL;
    pM : BOOL;
END_VAR

IF NOT estop THEN
    valveARun := FALSE;
    valveBRun := FALSE;
    valveCRun := FALSE;
    valveDRun := FALSE;
    mixMotorRun := FALSE;
    step := 0;
ELSIF NOT opeMode THEN
    step := 0;
    IF valveAStart AND NOT pA THEN valveARun := NOT valveARun; END_IF;
    IF valveBStart AND NOT pB THEN valveBRun := NOT valveBRun; END_IF;
    IF valveCStart AND NOT pC THEN valveCRun := NOT valveCRun; END_IF;
    IF valveDStart AND NOT pD THEN valveDRun := NOT valveDRun; END_IF;
    IF mixMotorStart AND NOT pM THEN mixMotorRun := NOT mixMotorRun; END_IF;
ELSE
    IF step = 0 THEN
        valveARun := FALSE;
    valveBRun := FALSE;
    valveCRun := FALSE;
    valveDRun := FALSE;
    mixMotorRun := FALSE;
        IF autoStart THEN step := 1; END_IF;
    END_IF;
    IF step = 1 THEN
        valveARun := TRUE;
        IF levelSensor >= 50 THEN valveARun := FALSE; step := 2; END_IF;
    END_IF;
    IF step = 2 THEN
        valveBRun := TRUE;
        IF levelSensor >= 80 THEN
            valveBRun := FALSE;
            IF processMode THEN step := 3; ELSE step := 4; END_IF;
        END_IF;
    END_IF;
    IF step = 3 THEN
        valveCRun := TRUE;
        IF levelSensor >= 100 THEN valveCRun := FALSE; step := 4; END_IF;
    END_IF;
    IF step = 4 THEN
        mixMotorRun := TRUE;
        IF mixMotorComplete THEN mixMotorRun := FALSE; valveDRun := TRUE; step := 5; END_IF;
    END_IF;
END_IF;
pA := valveAStart;
pB := valveBStart;
pC := valveCStart;
pD := valveDStart;
pM := mixMotorStart;
