(* Q02 Dual-Word Edge Detection - reference solution *)
FUNCTION_BLOCK E02_DualEdge
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
    r    : DWORD;
    f    : DWORD;
END_VAR

risingBits  := value AND NOT prev;
fallingBits := prev AND NOT value;
hasChanged  := value <> prev;
hasRisingEdges  := risingBits <> 0;
hasFallingEdges := fallingBits <> 0;

(* popcount without SHL: shift right by division, which keeps the
   implementation portable and works in the simulator *)
r := risingBits;
f := fallingBits;
noOfRisingBits  := 0;
noOfFallingBits := 0;
FOR i := 0 TO 31 DO
    IF (r MOD 2) <> 0 THEN
        noOfRisingBits := noOfRisingBits + 1;
    END_IF;
    IF (f MOD 2) <> 0 THEN
        noOfFallingBits := noOfFallingBits + 1;
    END_IF;
    r := r / 2;
    f := f / 2;
END_FOR;

prev := value;
