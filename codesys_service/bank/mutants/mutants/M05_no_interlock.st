FUNCTION_BLOCK M05_ProdLine
VAR_INPUT
    Mode : BOOL;
    ForwardButton : BOOL;
    ReverseButton : BOOL;
    SensorA : BOOL;
    SensorB : BOOL;
    SensorC : BOOL;
    ButtonA : BOOL;
    ButtonB : BOOL;
    ButtonC : BOOL;
END_VAR
VAR_OUTPUT
    MotorForward : BOOL;
    MotorReverse : BOOL;
    CompletionLight : BOOL;
END_VAR
VAR
    step : INT;   (* 0=at A waiting 1=A->B 2=at B waiting 3=B->C 4=at C done *)
    prevA : BOOL;
    prevB : BOOL;
    prevC : BOOL;
END_VAR

IF NOT Mode THEN
    (* manual mode with forward/reverse interlock *)
    MotorForward := ForwardButton;
    MotorReverse := ReverseButton;
    CompletionLight := FALSE;
ELSE
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
        (* step 4: at C *)
        MotorForward := FALSE;
        IF ButtonC AND NOT prevC THEN
            CompletionLight := TRUE;
        END_IF;
        IF NOT SensorC THEN
            CompletionLight := FALSE;
            step := 0;
        END_IF;
    END_IF;
END_IF;

prevA := ButtonA;
prevB := ButtonB;
prevC := ButtonC;
