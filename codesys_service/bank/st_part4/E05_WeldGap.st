(* Q05 Weld Gap Alarm and Startup Inhibition - reference solution *)
FUNCTION_BLOCK E05_WeldGap
VAR_INPUT
    Gap_Exceeded   : BOOL;
    Weld_E_Stop_NC : BOOL;
    DebounceTime   : TIME;
END_VAR
VAR_OUTPUT
    Operator_Alert        : BOOL;
    Weld_Soft_Start_Active: BOOL;
END_VAR
VAR
    initTimer : TON;
    debTimer  : TON;
    initDone  : BOOL;
END_VAR

initTimer(IN := Weld_E_Stop_NC AND NOT initDone, PT := T#5S);
IF initTimer.Q THEN
    initDone := TRUE;
END_IF;

IF NOT Weld_E_Stop_NC THEN
    Operator_Alert := FALSE;
    Weld_Soft_Start_Active := FALSE;
    debTimer(IN := FALSE, PT := DebounceTime);
ELSIF NOT initDone THEN
    Operator_Alert := FALSE;
    Weld_Soft_Start_Active := TRUE;
    debTimer(IN := FALSE, PT := DebounceTime);
ELSE
    Weld_Soft_Start_Active := FALSE;
    debTimer(IN := Gap_Exceeded, PT := DebounceTime);
    Operator_Alert := debTimer.Q;
END_IF;
