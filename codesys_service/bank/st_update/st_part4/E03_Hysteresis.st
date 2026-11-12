(* Q03 Alarm Handling - reference solution (used only to validate the test cases)
   Note: status codes are written in decimal (32769 = 16#8001, 32770 = 16#8002)
   because the offline simulator (st_sim) does not support typed literals. *)
FUNCTION_BLOCK E03_Hysteresis
VAR_INPUT
    Value      : REAL;
    hiLevel    : REAL;
    loLevel    : REAL;
    hystWindow : REAL;
END_VAR
VAR_OUTPUT
    hiAlarm : BOOL;
    loAlarm : BOOL;
    error   : BOOL;
    status  : WORD;
END_VAR

IF loLevel >= hiLevel THEN
    error  := TRUE;
    status := 32769;
ELSIF hystWindow >= hiLevel - loLevel THEN
    error  := TRUE;
    status := 32770;
ELSE
    error  := FALSE;
    status := 0;
    (* high alarm with hysteresis *)
    IF Value > hiLevel THEN
        hiAlarm := TRUE;
    ELSIF Value < hiLevel - hystWindow THEN
        hiAlarm := FALSE;
    END_IF;
    (* low alarm with hysteresis *)
    IF Value < loLevel THEN
        loAlarm := TRUE;
    ELSIF Value > loLevel + hystWindow THEN
        loAlarm := FALSE;
    END_IF;
END_IF;
