(* 逻辑有缺陷的版本：只处理了停止按钮，漏了急停 EStop。
   预期：TC01 通过，TC03 失败（急停不能停机）。 *)
PROGRAM PLC_PRG
VAR
    StartBtn : BOOL;
    StopBtn  : BOOL;
    EStop    : BOOL;
    Motor    : BOOL;
END_VAR

IF StartBtn AND NOT StopBtn THEN
    Motor := TRUE;
END_IF;

IF StopBtn THEN
    Motor := FALSE;
END_IF;
