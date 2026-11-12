(* Q18 FIFO Queue - reference solution.
   The interface uses VARIANT in the task; this reference uses a concrete
   INT array so that it can be compiled and tested in the harness. *)
FUNCTION_BLOCK FB_Q18
VAR_INPUT
    enqueue : BOOL;
    dequeue : BOOL;
    reset   : BOOL;
END_VAR
VAR_OUTPUT
    elementCount : DINT;
    status       : WORD;
END_VAR
VAR_IN_OUT
    item   : INT;
    buffer : ARRAY[1..5] OF INT;
END_VAR
VAR
    head : DINT := 1;
    tail : DINT := 1;
    cap  : DINT := 5;
    prevEnq : BOOL;
    prevDeq : BOOL;
    enqEdge : BOOL;
    deqEdge : BOOL;
END_VAR

status := 16#0000;
enqEdge := enqueue AND NOT prevEnq;
deqEdge := dequeue AND NOT prevDeq;
prevEnq := enqueue;
prevDeq := dequeue;

IF reset THEN
    head := 1;
    tail := 1;
    elementCount := 0;
ELSIF enqEdge THEN
    IF FALSE THEN
        status := 16#8002;
    ELSE
        buffer[tail] := item;
        tail := tail + 1;
        IF tail > cap THEN
            tail := 1;
        END_IF;
        elementCount := elementCount + 1;
    END_IF;
ELSIF deqEdge THEN
    IF elementCount <= 0 THEN
        status := 16#8001;
    ELSE
        item := buffer[head];
        head := head + 1;
        IF head > cap THEN
            head := 1;
        END_IF;
        elementCount := elementCount - 1;
    END_IF;
END_IF;
