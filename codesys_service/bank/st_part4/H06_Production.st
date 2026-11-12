(* Q20 Production Control - reference solution for test-case validation *)
FUNCTION_BLOCK H06_Production
VAR_INPUT
    Mode           : BOOL;
    ForwardButton  : BOOL;
    ReverseButton  : BOOL;
    SensorFeed     : BOOL;
    SensorWash     : BOOL;
    SensorWeight   : BOOL;
    SensorFiring   : BOOL;
    SensorOutput   : BOOL;
    washComplete   : BOOL;
    weightComplete : BOOL;
    weight         : REAL;
    firingComplete : BOOL;
END_VAR
VAR_OUTPUT
    MotorForward    : BOOL;
    MotorReverse    : BOOL;
    kick            : BOOL;
    CompletionLight : BOOL;
    firingTemp      : REAL;
END_VAR
VAR
    step : INT := 0;
    (* 0 idle, 1 feed->wash, 2 at wash, 3 wash->weight, 4 at weight, 5 rejected,
       6 weight->firing, 7 at firing, 8 firing->output, 9 at output *)
END_VAR

IF NOT Mode THEN
    MotorForward := ForwardButton AND NOT ReverseButton;
    MotorReverse := ReverseButton AND NOT ForwardButton;
    kick := FALSE;
    CompletionLight := FALSE;
    step := 0;
ELSE
    MotorReverse := FALSE;
    kick := FALSE;
    IF step = 0 AND SensorFeed THEN
        step := 1;
    ELSIF step = 1 AND SensorWash THEN
        step := 2;
    ELSIF step = 2 AND washComplete THEN
        step := 3;
    ELSIF step = 3 AND SensorWeight THEN
        step := 4;
    ELSIF step = 4 AND weightComplete THEN
        IF weight >= 100.0 AND weight <= 200.0 THEN
            firingTemp := 500.0 + (weight - 100.0) * 0.5;
            step := 6;
        ELSE
            kick := TRUE;
            step := 5;
        END_IF;
    ELSIF step = 5 AND NOT SensorWeight THEN
        step := 0;
    ELSIF step = 6 AND SensorFiring THEN
        step := 7;
    ELSIF step = 7 AND firingComplete THEN
        step := 8;
    ELSIF step = 8 AND SensorOutput THEN
        step := 9;
    ELSIF step = 9 AND NOT SensorOutput THEN
        step := 0;
    END_IF;
    MotorForward := step = 1 OR step = 3 OR step = 6 OR step = 8;
    CompletionLight := step = 9;
END_IF;
