FUNCTION_BLOCK E03_Hysteresis
VAR_INPUT
    Value : REAL;
    hiLevel : REAL;
    loLevel : REAL;
    hystWindow : REAL;
END_VAR
VAR_OUTPUT
    hiAlarm : BOOL;
    loAlarm : BOOL;
    error : BOOL;
    status : WORD;
END_VAR

IF loLevel >= hiLevel THEN
    error := TRUE;
    status := 16#8001;
    hiAlarm := FALSE;
    loAlarm := FALSE;
ELSIF FALSE THEN
    error := TRUE;
    status := 16#8002;
    hiAlarm := FALSE;
    loAlarm := FALSE;
ELSE
    error := FALSE;
    status := 16#0000;
    (* high alarm with hysteresis *)
    IF hiAlarm THEN
        IF Value < (hiLevel - hystWindow) THEN
            hiAlarm := FALSE;
        END_IF;
    ELSE
        IF Value > hiLevel THEN
            hiAlarm := TRUE;
        END_IF;
    END_IF;
    (* low alarm with hysteresis *)
    IF loAlarm THEN
        IF Value > (loLevel + hystWindow) THEN
            loAlarm := FALSE;
        END_IF;
    ELSE
        IF Value < loLevel THEN
            loAlarm := TRUE;
        END_IF;
    END_IF;
END_IF;
