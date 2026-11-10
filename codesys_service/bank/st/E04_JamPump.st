FUNCTION_BLOCK E04_JamPump
VAR_INPUT
    VISCOSITY_OK : BOOL;
    PASTE_E_STOP_NC : BOOL;
    DebounceTime : TIME;
    CycleTime : TIME;
END_VAR
VAR_OUTPUT
    VFD_RUN : BOOL;
    PUMP_MAINT_DUE : BOOL;
    PUMP_RUNTIME_ACC : LTIME;
END_VAR
VAR
    viscTimer : TON;
    viscValid : BOOL;
END_VAR

(* debounce: only counts while signal AND permissive are both TRUE,
   so an emergency stop clears incomplete timing immediately *)
viscTimer(IN := VISCOSITY_OK AND PASTE_E_STOP_NC, PT := DebounceTime);
viscValid := viscTimer.Q;

VFD_RUN := viscValid AND PASTE_E_STOP_NC;

IF VFD_RUN THEN
    PUMP_RUNTIME_ACC := PUMP_RUNTIME_ACC + TIME_TO_LTIME(CycleTime);
END_IF;

PUMP_MAINT_DUE := (PUMP_RUNTIME_ACC >= LTIME#500H);
