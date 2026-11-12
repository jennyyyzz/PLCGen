(* H04 FIFO Queue - reference solution.
   The interface uses VARIANT in the task; this reference uses a concrete
   array so that it can be compiled and tested in the harness.
   Buffer capacity is 8 (ARRAY[0..7] OF DINT), the convention settled with
   Part 2; the test cases assume exactly this. *)
FUNCTION_BLOCK H04_FIFO
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
    item   : DINT;
    buffer : ARRAY[0..7] OF DINT;
END_VAR
VAR
    head : DINT := 0;
    tail : DINT := 0;
    cap  : DINT := 8;   (* ARRAY[0..7] *)
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
    head := 0;
    tail := 0;
    elementCount := 0;
ELSIF enqEdge THEN
    IF elementCount >= cap THEN
        status := 16#8002;
    ELSE
        buffer[tail] := item;
        tail := tail + 1;
        IF tail >= cap THEN
            tail := 0;
        END_IF;
        elementCount := elementCount + 1;
    END_IF;
ELSIF deqEdge THEN
    IF elementCount <= 0 THEN
        status := 16#8001;
    ELSE
        item := buffer[head];
        head := head + 1;
        IF head >= cap THEN
            head := 0;
        END_IF;
        elementCount := elementCount - 1;
    END_IF;
END_IF;
