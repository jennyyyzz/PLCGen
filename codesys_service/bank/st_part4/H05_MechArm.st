(* Q19 Mechanical Arm Control - reference solution for test-case validation *)
FUNCTION_BLOCK H05_MechArm
VAR_INPUT
    ManualMode        : BOOL;
    SingleStepMode    : BOOL;
    SingleCycleMode   : BOOL;
    ContinuousMode    : BOOL;
    EmergencyStop     : BOOL;
    Start             : BOOL;
    DownButton        : BOOL;
    UpButton          : BOOL;
    LeftButton        : BOOL;
    RightButton       : BOOL;
    GripButton        : BOOL;
    ReleaseButton     : BOOL;
    DownLimitSwitch   : BOOL;
    UpLimitSwitch     : BOOL;
    LeftLimitSwitch   : BOOL;
    RightLimitSwitch  : BOOL;
    GripLimitSwitch   : BOOL;
    ReleaseLimitSwitch: BOOL;
END_VAR
VAR_OUTPUT
    MoveDown        : BOOL;
    MoveUp          : BOOL;
    MoveLeft        : BOOL;
    MoveRight       : BOOL;
    ActivateGrip    : BOOL;
    ActivateRelease : BOOL;
END_VAR
VAR
    step    : INT := 0;   (* 0 idle at top-left; 1 down 2 grip 3 up 4 right 5 down 6 release 7 up 8 left *)
    active  : BOOL;       (* current step is being executed *)
    pStart  : BOOL;
    startEdge : BOOL;
    stepDone : BOOL;
END_VAR

startEdge := Start AND NOT pStart;
pStart := Start;

MoveDown := FALSE;
MoveUp := FALSE;
MoveLeft := FALSE;
MoveRight := FALSE;
ActivateGrip := FALSE;
ActivateRelease := FALSE;

IF NOT EmergencyStop THEN
    active := FALSE;
    step := 0;
ELSIF ManualMode THEN
    active := FALSE;
    step := 0;
    MoveDown := DownButton AND NOT DownLimitSwitch;
    MoveUp := UpButton AND NOT UpLimitSwitch;
    MoveLeft := LeftButton AND NOT LeftLimitSwitch;
    MoveRight := RightButton AND NOT RightLimitSwitch;
    ActivateGrip := GripButton AND NOT GripLimitSwitch;
    ActivateRelease := ReleaseButton AND NOT ReleaseLimitSwitch;
ELSE
    (* start a step when idle *)
    IF NOT active THEN
        IF startEdge THEN
            IF step = 0 OR step = 8 THEN
                step := 1;
            ELSE
                step := step + 1;
            END_IF;
            active := TRUE;
        END_IF;
    END_IF;

    IF active THEN
        stepDone := FALSE;
        IF step = 1 OR step = 5 THEN
            MoveDown := NOT DownLimitSwitch;
            stepDone := DownLimitSwitch;
        ELSIF step = 2 THEN
            ActivateGrip := NOT GripLimitSwitch;
            stepDone := GripLimitSwitch;
        ELSIF step = 3 OR step = 7 THEN
            MoveUp := NOT UpLimitSwitch;
            stepDone := UpLimitSwitch;
        ELSIF step = 4 THEN
            MoveRight := NOT RightLimitSwitch;
            stepDone := RightLimitSwitch;
        ELSIF step = 6 THEN
            ActivateRelease := NOT ReleaseLimitSwitch;
            stepDone := ReleaseLimitSwitch;
        ELSIF step = 8 THEN
            MoveLeft := NOT LeftLimitSwitch;
            stepDone := LeftLimitSwitch;
        END_IF;

        IF stepDone THEN
            IF SingleStepMode THEN
                active := FALSE;                 (* wait for next Start *)
            ELSIF step < 8 THEN
                step := step + 1;                (* cycle modes: chain to next step *)
            ELSE
                step := 0;
                IF NOT ContinuousMode THEN
                    active := FALSE;             (* single cycle: stop at home *)
                ELSE
                    step := 1;                   (* continuous: restart *)
                END_IF;
            END_IF;
        END_IF;
    END_IF;
END_IF;
