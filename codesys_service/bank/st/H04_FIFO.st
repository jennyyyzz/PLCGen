(* 题面要求 item/buffer 为 VARIANT；纯 ST 无法对 VARIANT 做下标访问，
   此参考实现固定为 DINT / ARRAY[0..7] OF DINT 以验证逻辑，编译侧
   VARIANT 绑定能力另行验证。 *)
FUNCTION_BLOCK H04_FIFO
VAR_INPUT
    enqueue : BOOL;
    dequeue : BOOL;
    reset : BOOL;
END_VAR
VAR_OUTPUT
    elementCount : DINT;
    status : WORD;
END_VAR
VAR_IN_OUT
    item : DINT;
    buffer : ARRAY[0..7] OF DINT;
END_VAR
VAR
    head : DINT := 0;
    tail : DINT := 0;
    nq : DINT := 0;
    prevEnq : BOOL;
    prevDeq : BOOL;
    enqEdge : BOOL;
    deqEdge : BOOL;
END_VAR

IF reset THEN
    head := 0;
    tail := 0;
    nq := 0;
    elementCount := 0;
    status := 16#0000;
ELSE
    status := 16#0000;
    enqEdge := enqueue AND NOT prevEnq;
    deqEdge := dequeue AND NOT prevDeq;

    IF deqEdge THEN
        IF nq = 0 THEN
            status := 16#8001;   (* dequeue on empty queue *)
        ELSE
            item := buffer[head];
            head := head + 1;
            IF head > 7 THEN
                head := 0;
            END_IF;
            nq := nq - 1;
        END_IF;
    ELSIF enqEdge THEN
        IF nq >= 8 THEN
            status := 16#8002;   (* enqueue on full queue *)
        ELSE
            buffer[tail] := item;
            tail := tail + 1;
            IF tail > 7 THEN
                tail := 0;
            END_IF;
            nq := nq + 1;
        END_IF;
    END_IF;
    elementCount := nq;
END_IF;

prevEnq := enqueue;
prevDeq := dequeue;
