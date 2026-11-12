(* Q14 IPv4 Parsing with Format and Range Checks - reference solution *)
FUNCTION_BLOCK M08_IPv4
VAR_INPUT
    ipText : STRING(254);
END_VAR
VAR_OUTPUT
    ipValue : UDINT;
END_VAR
VAR
    i, n, segCount, digits, segVal : INT;
    ch : BYTE;
    acc : UDINT;
    ok : BOOL;
END_VAR

ipValue := 0;
acc := 0;
segCount := 0;
digits := 0;
segVal := 0;
ok := TRUE;
(* LEN avoids both WHILE and ADR: the simulator supports the Standard string
   functions and direct 1-based indexing of a STRING *)
n := LEN(ipText);

IF n > 0 THEN
FOR i := 1 TO n DO
    ch := ipText[i];
    IF ch >= 48 AND ch <= 57 THEN
        segVal := segVal * 10 + (BYTE_TO_INT(ch) - 48);
        digits := digits + 1;
        IF digits > 3 OR segVal > 255 THEN
            ok := FALSE;
        END_IF;
    ELSIF ch = 46 THEN
        IF digits = 0 THEN
            ok := FALSE;
        END_IF;
        acc := acc * 256 + INT_TO_UDINT(segVal);
        segCount := segCount + 1;
        segVal := 0;
        digits := 0;
        IF segCount > 3 THEN
            ok := FALSE;
        END_IF;
    ELSE
        ok := FALSE;
    END_IF;
END_FOR;
END_IF;

IF digits = 0 THEN
    ok := FALSE;
END_IF;
acc := acc * 256 + INT_TO_UDINT(segVal);
segCount := segCount + 1;

IF ok AND segCount = 4 THEN
    ipValue := acc;
END_IF;
