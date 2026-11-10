(* 故意写坏的一段 ST，用于验证静态检查能不能挡住低级错误。
   预期：E001（IF 未闭合）+ E004（= 当赋值用）+ W101（Motor2 未声明）+ W102（缺分号） *)
PROGRAM PLC_PRG_BAD
VAR
    StartBtn : BOOL;
    StopBtn  : BOOL;
    Motor    : BOOL;
END_VAR

IF StartBtn AND NOT StopBtn THEN
    Motor = TRUE
    Motor2 := TRUE;
