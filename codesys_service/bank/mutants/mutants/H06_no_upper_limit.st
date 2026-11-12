FUNCTION_BLOCK H06_Production
VAR_INPUT
    Mode : BOOL;
    ForwardButton : BOOL;
    ReverseButton : BOOL;
    SensorFeed : BOOL;
    SensorWash : BOOL;
    SensorWeight : BOOL;
    SensorFiring : BOOL;
    SensorOutput : BOOL;
    washComplete : BOOL;
    weightComplete : BOOL;
    weight : REAL;
    firingComplete : BOOL;
END_VAR
VAR_OUTPUT
    MotorForward : BOOL;
    MotorReverse : BOOL;
    kick : BOOL;
    CompletionLight : BOOL;
    firingTemp : REAL;
END_VAR
VAR
    step : INT;  (* 0=feed 1=feed->wash 2=wash wait 3=wash->weight 4=weigh
                    5=weight->(kick|fire) 6=fire wait 7=fire->out 8=done *)
    qualified : BOOL;
    prevWashC : BOOL;
    prevWeightC : BOOL;
    prevFireC : BOOL;
END_VAR

IF NOT Mode THEN
    MotorForward := ForwardButton AND NOT ReverseButton;
    MotorReverse := ReverseButton AND NOT ForwardButton;
    kick := FALSE;
    CompletionLight := FALSE;
    step := 0;
ELSE
    MotorReverse := FALSE;
    IF step = 0 THEN
        MotorForward := FALSE;
        kick := FALSE;
        IF SensorFeed THEN
            step := 1;
        END_IF;
    ELSIF step = 1 THEN
        MotorForward := TRUE;
        IF SensorWash THEN
            MotorForward := FALSE;
            step := 2;
        END_IF;
    ELSIF step = 2 THEN
        MotorForward := FALSE;
        IF washComplete AND NOT prevWashC THEN
            step := 3;
        END_IF;
    ELSIF step = 3 THEN
        MotorForward := TRUE;
        IF SensorWeight THEN
            MotorForward := FALSE;
            step := 4;
        END_IF;
    ELSIF step = 4 THEN
        MotorForward := FALSE;
        IF weightComplete AND NOT prevWeightC THEN
            qualified := (weight >= 100.0);
            IF qualified THEN
                (* 100..200 kg -> 500..550 degrees, linear *)
                firingTemp := 500.0 + (weight - 100.0) * 0.5;
                step := 5;
            ELSE
                kick := TRUE;
                step := 8;
            END_IF;
        END_IF;
    ELSIF step = 5 THEN
        MotorForward := TRUE;
        IF SensorFiring THEN
            MotorForward := FALSE;
            step := 6;
        END_IF;
    ELSIF step = 6 THEN
        MotorForward := FALSE;
        IF firingComplete AND NOT prevFireC THEN
            step := 7;
        END_IF;
    ELSIF step = 7 THEN
        MotorForward := TRUE;
        IF SensorOutput THEN
            MotorForward := FALSE;
            step := 8;
        END_IF;
    ELSE
        (* step 8: finished / rejected *)
        MotorForward := FALSE;
        CompletionLight := SensorOutput;
        IF NOT SensorOutput THEN
            CompletionLight := FALSE;
            kick := FALSE;
            step := 0;
        END_IF;
    END_IF;
END_IF;

prevWashC := washComplete;
prevWeightC := weightComplete;
prevFireC := firingComplete;
