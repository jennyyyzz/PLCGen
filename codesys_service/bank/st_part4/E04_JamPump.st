(* Q04 Jam Pump Debouncing and Runtime Maintenance - reference solution
   Unit convention: TIME inputs in ms, LTIME output in ns (IEC 61131-3). *)
FUNCTION_BLOCK E04_JamPump
VAR_INPUT
    VISCOSITY_OK    : BOOL;
    PASTE_E_STOP_NC : BOOL;
    DebounceTime    : TIME;
    CycleTime       : TIME;
END_VAR
VAR_OUTPUT
    VFD_RUN          : BOOL;
    PUMP_MAINT_DUE   : BOOL;
    PUMP_RUNTIME_ACC : LTIME;
END_VAR
VAR
    debT    : TON;     (* real elapsed time, scan-clock driven *)
    accMs   : ULINT;   (* ms, per the team convention *)
END_VAR

(* VISCOSITY_OK must hold continuously for DebounceTime (real elapsed time) *)
debT(IN := VISCOSITY_OK AND PASTE_E_STOP_NC, PT := DebounceTime);
VFD_RUN := debT.Q AND PASTE_E_STOP_NC;

IF VFD_RUN THEN
    accMs := accMs + UDINT_TO_ULINT(TIME_TO_UDINT(CycleTime));
    PUMP_RUNTIME_ACC := ULINT_TO_LTIME(accMs);
END_IF;

IF accMs >= 1800000000 THEN   (* 500 h in ms *)
    PUMP_MAINT_DUE := TRUE;
END_IF;
