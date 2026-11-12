(* Q02 Dual-Word Edge Detection - reference solution *)
FUNCTION_BLOCK FB_Q02
VAR_INPUT
    value : DWORD;
END_VAR
VAR_OUTPUT
    hasChanged      : BOOL;
    hasRisingEdges  : BOOL;
    risingBits      : DWORD;
    noOfRisingBits  : USINT;
    hasFallingEdges : BOOL;
    fallingBits     : DWORD;
    noOfFallingBits : USINT;
END_VAR
VAR
    prev : DWORD;
    i    : INT;
    m    : DWORD;
END_VAR

risingBits  := value;
fallingBits := prev AND NOT value;
hasChanged  := value <> prev;
hasRisingEdges  := risingBits <> 0;
hasFallingEdges := fallingBits <> 0;

noOfRisingBits  := 0;
noOfFallingBits := 0;
FOR i := 0 TO 31 DO
    m := SHL(DWORD#1, i);
    IF (risingBits AND m) <> 0 THEN
        noOfRisingBits := noOfRisingBits + 1;
    END_IF;
    IF (fallingBits AND m) <> 0 THEN
        noOfFallingBits := noOfFallingBits + 1;
    END_IF;
END_FOR;

prev := value;
