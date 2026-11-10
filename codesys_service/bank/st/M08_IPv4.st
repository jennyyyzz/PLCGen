FUNCTION_BLOCK M08_IPv4
VAR_INPUT
    ipText : STRING(254);
END_VAR
VAR_OUTPUT
    ipValue : UDINT;
END_VAR
VAR
    i : INT;
    ch : BYTE;
    seg : DINT;
    segCount : INT;
    started : BOOL;
    ok : BOOL;
    acc : DINT;
    slen : INT;
END_VAR

(* Standard Library: LEN gives the number of characters; the STRING itself
   is indexed directly (1-based) to avoid repeated MID copies. *)
ipValue := 0;
ok := TRUE;
seg := 0;
segCount := 0;
started := FALSE;
acc := 0;
slen := LEN(ipText);

FOR i := 1 TO slen DO
    ch := ipText[i];
    IF ch = 46 THEN
        (* '.' separator *)
        IF (NOT started) OR (seg > 255) OR (segCount = 4) THEN
            ok := FALSE;
        ELSE
            acc := acc * 256 + seg;
            segCount := segCount + 1;
            seg := 0;
            started := FALSE;
        END_IF;
    ELSIF (ch >= 48) AND (ch <= 57) THEN
        (* decimal digit *)
        seg := seg * 10 + (ch - 48);
        started := TRUE;
    ELSE
        ok := FALSE;
    END_IF;
END_FOR;

(* final segment must be present and in range; exactly 4 segments total *)
IF (NOT started) OR (seg > 255) OR (segCount <> 3) THEN
    ok := FALSE;
END_IF;

IF ok THEN
    acc := acc * 256 + seg;
    ipValue := DINT_TO_UDINT(acc);
ELSE
    ipValue := 0;
END_IF;
