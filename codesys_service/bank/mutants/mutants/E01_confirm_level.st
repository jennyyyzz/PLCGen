FUNCTION_BLOCK E01_Filling
VAR_INPUT
    bottleSensor : BOOL;
    cleaningConfirmButton : BOOL;
    fillingConfirmButton : BOOL;
    cappingConfirmButton : BOOL;
    packingConfirmButton : BOOL;
    finishedButton : BOOL;
END_VAR
VAR_OUTPUT
    Pump_Motor : BOOL;
    Filling_Valve : BOOL;
    Capping_Machine : BOOL;
    Packing_Machine : BOOL;
    Completion_Light : BOOL;
END_VAR
VAR
    step : INT;      (* 0=idle 1=cleaning 2=filling 3=capping 4=packing 5=done *)
    prevBottle : BOOL;
    prevCleaning : BOOL;
    prevFilling : BOOL;
    prevCapping : BOOL;
    prevPacking : BOOL;
    prevFinished : BOOL;
END_VAR

(* step transitions on rising edges *)
IF step = 0 AND bottleSensor AND NOT prevBottle THEN
    step := 1;
END_IF;
IF step = 1 AND cleaningConfirmButton THEN
    step := 2;
END_IF;
IF step = 2 AND fillingConfirmButton THEN
    step := 3;
END_IF;
IF step = 3 AND cappingConfirmButton THEN
    step := 4;
END_IF;
IF step = 4 AND packingConfirmButton THEN
    step := 5;
END_IF;
IF step = 5 AND finishedButton AND NOT prevFinished THEN
    step := 0;
END_IF;

(* outputs by step *)
Pump_Motor := (step = 1);
Filling_Valve := (step = 2);
Capping_Machine := (step = 3);
Packing_Machine := (step = 4);
Completion_Light := (step = 5);

prevBottle := bottleSensor;
prevCleaning := cleaningConfirmButton;
prevFilling := fillingConfirmButton;
prevCapping := cappingConfirmButton;
prevPacking := packingConfirmButton;
prevFinished := finishedButton;
