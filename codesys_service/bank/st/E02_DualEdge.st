FUNCTION_BLOCK E02_DualEdge
VAR_INPUT
    value : DWORD;
END_VAR
VAR_OUTPUT
    hasChanged : BOOL;
    hasRisingEdges : BOOL;
    risingBits : DWORD;
    noOfRisingBits : USINT;
    hasFallingEdges : BOOL;
    fallingBits : DWORD;
    noOfFallingBits : USINT;
END_VAR
VAR
    prevValue : DWORD;
    i : INT;
    tr : DWORD;
    tf : DWORD;
    cntR : USINT;
    cntF : USINT;
END_VAR

risingBits := value AND (NOT prevValue);
fallingBits := (NOT value) AND prevValue;
hasChanged := (value <> prevValue);
hasRisingEdges := (risingBits <> 0);
hasFallingEdges := (fallingBits <> 0);

(* popcount without SHL: shift right by division *)
cntR := 0;
tr := risingBits;
FOR i := 0 TO 31 DO
    IF (tr MOD 2) = 1 THEN
        cntR := cntR + 1;
    END_IF;
    tr := tr / 2;
END_FOR;

cntF := 0;
tf := fallingBits;
FOR i := 0 TO 31 DO
    IF (tf MOD 2) = 1 THEN
        cntF := cntF + 1;
    END_IF;
    tf := tf / 2;
END_FOR;

noOfRisingBits := cntR;
noOfFallingBits := cntF;
prevValue := value;
