(* ============================================================
   示例：电机启停控制（对应大作业第六章示例题）
   文件约定：包含 POU 头 + VAR 声明 + 实现体，
   结尾不写 END_PROGRAM（CODESYS 文本化 POU 中它是隐含的）。
   ============================================================ *)
PROGRAM PLC_PRG
VAR
    StartBtn : BOOL;   (* 启动按钮 *)
    StopBtn  : BOOL;   (* 停止按钮 *)
    EStop    : BOOL;   (* 急停信号 *)
    Motor    : BOOL;   (* 电机运行输出 *)
END_VAR

(* 停止/急停优先级高于启动；启动按钮松开后由 Motor 自保持 *)
IF (StopBtn OR EStop) THEN
    Motor := FALSE;
ELSIF (StartBtn AND NOT StopBtn AND NOT EStop) THEN
    Motor := TRUE;
END_IF;
