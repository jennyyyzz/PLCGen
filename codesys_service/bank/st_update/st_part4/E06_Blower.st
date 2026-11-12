(* Q06 Aeration Blower Delayed Start - reference solution *)
FUNCTION_BLOCK E06_Blower
VAR_INPUT
    DO_LOW               : BOOL;
    AERATION_E_STOP_NC   : BOOL;
END_VAR
VAR_OUTPUT
    BLOWER_RUN                  : BOOL;
    AERATION_BLOWER_CYCLE_COUNT : UINT;
END_VAR
VAR
    startTimer : TON;
    prevRun    : BOOL;
END_VAR

startTimer(IN := DO_LOW AND AERATION_E_STOP_NC, PT := T#5S);
BLOWER_RUN := startTimer.Q;

IF BLOWER_RUN AND NOT prevRun THEN
    AERATION_BLOWER_CYCLE_COUNT := AERATION_BLOWER_CYCLE_COUNT + 1;
END_IF;
prevRun := BLOWER_RUN;
