FUNCTION_BLOCK M03_MovingAvg
VAR_INPUT
    cyclicExecution : BOOL;
    trigger : BOOL;
    value : LREAL;
    windowSize : INT;
    reset : BOOL;
END_VAR
VAR_OUTPUT
    average : LREAL;
    windowSizeReached : BOOL;
    error : BOOL;
    status : WORD;
END_VAR
VAR
    buf : ARRAY[1..100] OF LREAL;
    idx : INT := 1;
    filled : INT := 0;
    sum : LREAL := 0.0;
    prevTrigger : BOOL;
    doUpdate : BOOL;
END_VAR

IF (windowSize < 1) OR (windowSize > 100) THEN
    error := TRUE;
    status := 16#8200;
    average := 0.0;
    windowSizeReached := FALSE;
ELSIF reset THEN
    filled := 0;
    idx := 1;
    sum := 0.0;
    average := 0.0;
    windowSizeReached := FALSE;
    error := FALSE;
    status := 16#0000;
ELSE
    error := FALSE;
    status := 16#0000;
    doUpdate := cyclicExecution OR (trigger AND NOT prevTrigger);
    IF doUpdate THEN
        IF filled < windowSize THEN
            (* filling phase: plain average of received values *)
            buf[idx] := value;
            sum := sum + value;
            filled := filled + 1;
            idx := idx + 1;
            IF idx > windowSize THEN
                idx := 1;
            END_IF;
            average := sum / INT_TO_LREAL(filled);
            windowSizeReached := (filled >= windowSize);
        ELSE
            (* steady state: replace oldest, recompute *)
            sum := sum - buf[idx] + value;
            buf[idx] := value;
            idx := idx + 1;
            IF idx > windowSize THEN
                idx := 1;
            END_IF;
            average := sum / INT_TO_LREAL(windowSize);
            windowSizeReached := TRUE;
        END_IF;
    END_IF;
END_IF;

prevTrigger := trigger;
