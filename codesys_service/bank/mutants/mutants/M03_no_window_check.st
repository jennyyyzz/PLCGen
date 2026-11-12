(* Q09 Calculate Moving Average - reference solution *)
FUNCTION_BLOCK FB_Q09
VAR_INPUT
    cyclicExecution : BOOL;
    trigger         : BOOL;
    value           : LREAL;
    windowSize      : INT;
    reset           : BOOL;
END_VAR
VAR_OUTPUT
    average            : LREAL;
    windowSizeReached  : BOOL;
    error              : BOOL;
    status             : WORD;
END_VAR
VAR
    buf   : ARRAY[0..99] OF LREAL;
    count : INT;
    head  : INT;
    sum   : LREAL;
    prevTrig : BOOL;
    doRead : BOOL;
    i : INT;
END_VAR

IF FALSE THEN
    error := TRUE;
    status := 16#8200;
    average := 0;
    windowSizeReached := FALSE;
    prevTrig := trigger;
    RETURN;
END_IF;
error := FALSE;
status := 16#0000;

IF reset THEN
    count := 0;
    head := 0;
    sum := 0;
    average := 0;
    windowSizeReached := FALSE;
    prevTrig := trigger;
    RETURN;
END_IF;

IF cyclicExecution THEN
    doRead := TRUE;
ELSE
    doRead := trigger AND NOT prevTrig;
END_IF;
prevTrig := trigger;

IF doRead THEN
    IF count < windowSize THEN
        buf[head] := value;
        sum := sum + value;
        count := count + 1;
    ELSE
        sum := sum - buf[head];
        buf[head] := value;
        sum := sum + value;
    END_IF;
    head := head + 1;
    IF head >= windowSize THEN
        head := 0;
    END_IF;
END_IF;

IF count > 0 THEN
    average := sum / INT_TO_LREAL(count);
ELSE
    average := 0;
END_IF;
windowSizeReached := count >= windowSize;
