FUNCTION_BLOCK E05_WeldGap
VAR_INPUT
    Gap_Exceeded : BOOL;
    Weld_E_Stop_NC : BOOL;
    DebounceTime : TIME;
END_VAR
VAR_OUTPUT
    Operator_Alert : BOOL;
    Weld_Soft_Start_Active : BOOL;
END_VAR
VAR
    initTimer : TON;
    gapTimer : TON;
    initDone : BOOL;
END_VAR

(* 5s power-up inhibition; e-stop freezes it (IN=FALSE) *)
initTimer(IN := Weld_E_Stop_NC AND NOT initDone, PT := T#5S);
IF initTimer.Q THEN
    initDone := TRUE;
END_IF;

Weld_Soft_Start_Active := (NOT initDone) AND Weld_E_Stop_NC;

(* gap monitoring only after init, only while no e-stop;
   IN=FALSE on signal loss / e-stop clears the timing automatically *)
gapTimer(IN := Weld_E_Stop_NC AND initDone AND Gap_Exceeded, PT := DebounceTime);
Operator_Alert := gapTimer.Q AND Weld_E_Stop_NC AND initDone;
