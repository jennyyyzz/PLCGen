(* Q04 Jam Pump Debouncing and Runtime Maintenance - reference solution
   Unit convention: TIME inputs in ms, LTIME output in ns (IEC 61131-3). *)
FUNCTION_BLOCK FB_Q04
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
    debAcc  : UDINT;   (* ms *)
    accNs   : ULINT;   (* ns *)
END_VAR

IF NOT PASTE_E_STOP_NC THEN
    VFD_RUN := FALSE;
    debAcc := 0;
ELSE
    IF VISCOSITY_OK THEN
        debAcc := debAcc + TIME_TO_UDINT(CycleTime);
    ELSE
        debAcc := 0;
    END_IF;
    VFD_RUN := VISCOSITY_OK;
END_IF;

IF VFD_RUN THEN
    accNs := accNs + UDINT_TO_ULINT(TIME_TO_UDINT(CycleTime)) * 1000000;
    PUMP_RUNTIME_ACC := ULINT_TO_LTIME(accNs);
END_IF;

IF accNs >= 1800000000000000 THEN
    PUMP_MAINT_DUE := TRUE;
END_IF;
