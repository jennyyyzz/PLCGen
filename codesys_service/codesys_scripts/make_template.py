# -*- coding: utf-8 -*-
"""在 CODESYS ScriptEngine 内运行：从零生成一个「可编译」的模板工程。

由 codesys_compile.py --make-template 调用。

关键点（实测 SP22）：
  - 只有「设备 + Application」还不够：没有任务配置时 app.build() 会跳过 POU，
    任何代码都报 0 错误（假通过）。必须建 Task Configuration + MainTask，
    并把 POU 挂到任务的调用列表里。
  - 设备用 CODESYS Control Win V3 x64（自带 Standard.project 用的是老 PLCWinNT，
    缺 IoStandard 库，一编译就 16 个错误，不能当模板）。
"""
import io
import json
import re
import sys
import traceback

PROGRESS = re.compile(r"(开始构建|代码典型化|编译完成|生成代码|正在准备|正在编译)")


def load_args():
    for a in reversed(sys.argv[1:]):
        a = str(a).strip().strip('"')
        if not a:
            continue
        if a.startswith("{"):
            return json.loads(a)
        if a.lower().endswith(".json"):
            fh = io.open(a, "r", encoding="utf-8")
            try:
                return json.load(fh)
            finally:
                fh.close()
    return {}


def find_device(wanted):
    dr = globals().get("device_repository")
    names = []
    for dev in dr.get_all_devices():
        try:
            nm = str(dev.device_info.name)
        except Exception:
            continue
        if nm not in names:
            names.append(nm)
        if nm == wanted:
            return dev.device_id, names
    for dev in dr.get_all_devices():
        try:
            nm = str(dev.device_info.name)
        except Exception:
            continue
        if wanted.lower() in nm.lower():
            return dev.device_id, names
    return None, names


def build_messages(system):
    """返回 (错误数, 警告数, 错误文本列表)。SP22 的消息是纯字符串。"""
    errs, warns, texts = 0, 0, []
    for cat in system.get_message_categories():
        try:
            msgs = [str(m) for m in system.get_messages(cat)]
        except Exception:
            continue
        for s in msgs:
            m = re.search(r"(\d+)\s*错误\s*[,，]\s*(\d+)\s*警告", s)
            if m:
                errs = int(m.group(1))
                warns = int(m.group(2))
                continue
            if PROGRESS.search(s) or s.startswith("------"):
                continue
            if "离线帮助" in s:
                continue
            texts.append(s[:200])
    return errs, warns, texts


def main():
    args = load_args()
    out_project = args.get("out") or r"C:\Temp\codesys_template.project"
    device_name = args.get("device") or "CODESYS Control Win V3 x64"
    report_path = args.get("report")

    result = {"ok": False, "project": out_project, "device": device_name,
              "steps": {}, "error": None}

    try:
        dev_id, names = find_device(device_name)
        if dev_id is None:
            result["error"] = ("device not found: %s. e.g. %s"
                               % (device_name, ", ".join(names[:12])))
            raise SystemExit(1)
        result["steps"]["device_id"] = str(dev_id)

        proj = projects.create(out_project, True)
        proj.add("Device", dev_id, "")
        app = proj.active_application

        # POU
        plc = None
        for obj in proj.get_children(True):
            try:
                if str(obj.get_name()) == "PLC_PRG" and hasattr(obj, "textual_declaration"):
                    plc = obj
            except Exception:
                pass
        if plc is None:
            plc = app.create_pou("PLC_PRG", PouType.Program, ImplementationLanguages.st)
        plc.textual_declaration.replace("PROGRAM PLC_PRG\nVAR\nEND_VAR")
        plc.textual_implementation.replace(";")
        result["steps"]["pou"] = "PLC_PRG"

        # 任务配置 + 任务 + 调用列表（缺了这一步编译等于空转）
        tc = app.create_task_configuration()
        task = tc.create_task("MainTask")
        task.pous.add("PLC_PRG")
        result["steps"]["task"] = "MainTask -> PLC_PRG"

        system = globals().get("system")
        app.build()
        errs, warns, texts = build_messages(system)
        result["steps"]["build"] = {"errors": errs, "warnings": warns,
                                    "texts": texts[:5]}
        result["ok"] = (errs == 0)

        proj.save()
        proj.close()
    except SystemExit:
        pass
    except Exception:
        result["error"] = traceback.format_exc()

    if report_path:
        fh = io.open(report_path, "w", encoding="utf-8")
        try:
            fh.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        finally:
            fh.close()
    try:
        print("[make-template] ok=%s build=%s"
              % (result["ok"], json.dumps(result["steps"].get("build"), ensure_ascii=False)))
    except Exception:
        pass


main()
