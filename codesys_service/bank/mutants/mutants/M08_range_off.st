(* Q14 IPv4 Parsing with Format and Range Checks - reference solution *)
FUNCTION_BLOCK FB_Q14
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
    pText : POINTER TO BYTE;
END_VAR

ipValue := 0;
acc := 0;
segCount := 0;
digits := 0;
segVal := 0;
ok := TRUE;
pText := ADR(ipText);
n := 0;
WHILE n < 254 AND pText[n] <> 0 DO
    n := n + 1;
END_WHILE;

IF n = 0 THEN
    RETURN;
END_IF;

FOR i := 0 TO n - 1 DO
    ch := pText[i];
    IF ch >= 48 AND ch <= 57 THEN
        segVal := segVal * 10 + (BYTE_TO_INT(ch) - 48);
        digits := digits + 1;
        IF digits > 3 OR segVal > 256 THEN
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

IF digits = 0 THEN
    ok := FALSE;
END_IF;
acc := acc * 256 + INT_TO_UDINT(segVal);
segCount := segCount + 1;

IF ok AND segCount = 4 THEN
    ipValue := acc;
END_IF;
