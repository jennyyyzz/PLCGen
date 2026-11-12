(* Q11 Automated Production Line Control - reference solution for test-case validation *)
FUNCTION_BLOCK M05_ProdLine
VAR_INPUT
    Mode          : BOOL;
    ForwardButton : BOOL;
    ReverseButton : BOOL;
    SensorA       : BOOL;
    SensorB       : BOOL;
    SensorC       : BOOL;
    ButtonA       : BOOL;
    ButtonB       : BOOL;
    ButtonC       : BOOL;
END_VAR
VAR_OUTPUT
    MotorForward    : BOOL;
    MotorReverse    : BOOL;
    CompletionLight : BOOL;
END_VAR
VAR
    step : INT := 0;  (* 0 wait at A, 1 move A->B, 2 wait at B, 3 move B->C, 4 at C, 5 done *)
    prevA : BOOL;
    prevB : BOOL;
    prevC : BOOL;
    shownStep : INT := 0;   (* the step whose outputs are being driven *)
END_VAR

IF NOT Mode THEN
    (* manual: interlocked jog *)
    MotorForward := ForwardButton AND NOT ReverseButton;
    MotorReverse := ReverseButton AND NOT ForwardButton;
    CompletionLight := FALSE;
    step := 0;
ELSE
    (* Automatic mode.  The motor outputs are assigned inside each step branch and
       cleared in the same scan a transition happens, so the output of a newly
       entered step only appears from the next scan onwards.
       Station buttons are edge-triggered: a button already held when the carriage
       arrives has no rising edge and must not release it. *)
    MotorReverse := FALSE;

    IF step = 0 THEN
        MotorForward := FALSE;
        IF SensorA AND ButtonA AND NOT prevA THEN
            step := 1;
        END_IF;
    ELSIF step = 1 THEN
        MotorForward := TRUE;
        IF SensorB THEN
            MotorForward := FALSE;
            step := 2;
        END_IF;
    ELSIF step = 2 THEN
        MotorForward := FALSE;
        IF ButtonB AND NOT prevB THEN
            step := 3;
        END_IF;
    ELSIF step = 3 THEN
        MotorForward := TRUE;
        IF SensorC THEN
            MotorForward := FALSE;
            step := 4;
        END_IF;
    ELSE
        MotorForward := FALSE;
        IF ButtonC AND NOT prevC THEN
            CompletionLight := TRUE;
        END_IF;
        IF NOT SensorC THEN
            CompletionLight := FALSE;
            step := 0;
        END_IF;
    END_IF;

    prevA := ButtonA;
    prevB := ButtonB;
    prevC := ButtonC;
END_IF;
