FUNCTION_BLOCK H05_MechArm
VAR_INPUT
    ManualMode : BOOL;
    SingleStepMode : BOOL;
    SingleCycleMode : BOOL;
    ContinuousMode : BOOL;
    EmergencyStop : BOOL;
    Start : BOOL;
    DownButton : BOOL;
    UpButton : BOOL;
    LeftButton : BOOL;
    RightButton : BOOL;
    GripButton : BOOL;
    ReleaseButton : BOOL;
    DownLimitSwitch : BOOL;
    UpLimitSwitch : BOOL;
    LeftLimitSwitch : BOOL;
    RightLimitSwitch : BOOL;
    GripLimitSwitch : BOOL;
    ReleaseLimitSwitch : BOOL;
END_VAR
VAR_OUTPUT
    MoveDown : BOOL;
    MoveUp : BOOL;
    MoveLeft : BOOL;
    MoveRight : BOOL;
    ActivateGrip : BOOL;
    ActivateRelease : BOOL;
END_VAR
VAR
    step : INT := 0;   (* 0 idle, then 1..8 = the 8-action cycle *)
    prevStart : BOOL;
    running : BOOL;
END_VAR

MoveDown := FALSE;
MoveUp := FALSE;
MoveLeft := FALSE;
MoveRight := FALSE;
ActivateGrip := FALSE;
ActivateRelease := FALSE;

IF NOT EmergencyStop THEN
    (* emergency stop: all actions off, sequence aborted *)
    step := 0;
    running := FALSE;
ELSIF ManualMode THEN
    (* manual: buttons drive actions, limited by position switches *)
    MoveDown := DownButton AND NOT DownLimitSwitch;
    MoveUp := UpButton AND NOT UpLimitSwitch;
    MoveLeft := LeftButton AND NOT LeftLimitSwitch;
    MoveRight := RightButton AND NOT RightLimitSwitch;
    ActivateGrip := GripButton AND NOT GripLimitSwitch;
    ActivateRelease := ReleaseButton AND NOT ReleaseLimitSwitch;
    step := 0;
    running := FALSE;
ELSIF SingleStepMode THEN
    (* single step: each start press advances one action *)
    IF Start AND NOT prevStart AND NOT running THEN
        IF step = 0 THEN
            step := 1;
        END_IF;
    END_IF;
    IF step > 0 THEN
        running := TRUE;
    END_IF;
ELSE
    (* single cycle / continuous: run through the cycle automatically *)
    IF (Start AND NOT prevStart) AND (step = 0) THEN
        step := 1;
    END_IF;
    IF step > 0 THEN
        running := TRUE;
    END_IF;
END_IF;

IF running AND EmergencyStop THEN
    (* action execution by step; each step stops on its completion feedback *)
    IF step = 1 THEN
        MoveDown := NOT DownLimitSwitch;
        IF DownLimitSwitch THEN step := 2; END_IF;
    ELSIF step = 2 THEN
        ActivateGrip := NOT GripLimitSwitch;
        IF GripLimitSwitch THEN step := 3; END_IF;
    ELSIF step = 3 THEN
        MoveUp := NOT UpLimitSwitch;
        IF UpLimitSwitch THEN step := 4; END_IF;
    ELSIF step = 4 THEN
        MoveRight := NOT RightLimitSwitch;
        IF RightLimitSwitch THEN step := 5; END_IF;
    ELSIF step = 5 THEN
        MoveDown := NOT DownLimitSwitch;
        IF DownLimitSwitch THEN step := 6; END_IF;
    ELSIF step = 6 THEN
        ActivateRelease := NOT ReleaseLimitSwitch;
        IF ReleaseLimitSwitch THEN step := 7; END_IF;
    ELSIF step = 7 THEN
        MoveUp := NOT UpLimitSwitch;
        IF UpLimitSwitch THEN step := 8; END_IF;
    ELSIF step = 8 THEN
        MoveLeft := NOT LeftLimitSwitch;
        IF LeftLimitSwitch THEN
            (* cycle complete: single cycle stops, continuous restarts *)
            IF ContinuousMode THEN
                step := 1;
            ELSE
                step := 0;
                running := FALSE;
            END_IF;
        END_IF;
    ELSE
        running := FALSE;
    END_IF;

    (* single step pauses between actions after completing one *)
    IF SingleStepMode AND (step > 1) THEN
        (* stop execution after the current action finishes:
           handled implicitly on the next invocation *)
        running := FALSE;
        step := step;  (* hold position, wait for next start *)
    END_IF;
END_IF;

prevStart := Start;
