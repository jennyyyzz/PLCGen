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

# ---------------------------------------------------------------------------
# Standard Library 引用（正解，2026-11-10 实测）
#
# 背景：本机其实装着 Standard Library：
#   C:\ProgramData\CODESYS\Managed Libraries\System\Standard\3.5.22.0
# 之前 `lm.add_library("Standard, * (System)")` 只写引用不装载（noUI 下
# 后台装载不启动），编译仍报「未知的类型: 'TON'」。
# 正确姿势：用全局 librarymanager 模块从仓库拿到真实库对象，再
#   libman.add_placeholder("Standard", lib)
# 占位符在 build 时解析，真库生效 —— TON/TOF/TP/LEN/MID 等全部可编译。
# 若目标机器仓库里没有 Standard（找不到库对象），回退到 TON/TOF/TP 编译桩。
# ---------------------------------------------------------------------------
def ensure_standard_library(proj):
    """在工程的库管理器里引用真 Standard Library。成功返回 True。"""
    libman = None
    for obj in proj.get_children(True):
        try:
            if getattr(obj, "is_libman", False):
                libman = obj
                break
        except Exception:
            pass
    if libman is None:
        return False
    # 已引用过（重开工程/重复生成）就不重复加。
    # 注意不能用子串匹配：#IoStandard 里也含 "Standard"。
    try:
        for ref in libman.get_libraries():
            try:
                nm = str(ref).lstrip("#").split(",")[0].strip()
                if nm == "Standard":
                    return True
            except Exception:
                pass
    except Exception:
        pass
    lmg = globals().get("librarymanager")
    if lmg is None:
        return False
    try:
        for repo in lmg.repositories:
            for lib in lmg.get_all_libraries(repo):
                try:
                    if str(lib.title) == "Standard":
                        libman.add_placeholder("Standard", lib)
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# TON / TOF / TP 编译桩（Standard Library 不可用时的回退方案）
# ---------------------------------------------------------------------------
TIMER_STUBS = {
    "TON": ("""FUNCTION_BLOCK TON
VAR_INPUT
    IN : BOOL;
    PT : TIME;
END_VAR
VAR_OUTPUT
    Q : BOOL;
    ET : TIME;
END_VAR""",
"""(* Compile-only stub provided by the toolchain service. *)
(* Real timer semantics are implemented by the sim backend (st_sim.py). *)
Q := IN AND (ET >= PT);
ET := T#0S;"""),
    "TOF": ("""FUNCTION_BLOCK TOF
VAR_INPUT
    IN : BOOL;
    PT : TIME;
END_VAR
VAR_OUTPUT
    Q : BOOL;
    ET : TIME;
END_VAR""",
"""(* Compile-only stub provided by the toolchain service. *)
(* Real timer semantics are implemented by the sim backend (st_sim.py). *)
Q := IN OR (ET < PT);
ET := T#0S;"""),
    "TP": ("""FUNCTION_BLOCK TP
VAR_INPUT
    IN : BOOL;
    PT : TIME;
END_VAR
VAR_OUTPUT
    Q : BOOL;
    ET : TIME;
END_VAR""",
"""(* Compile-only stub provided by the toolchain service. *)
(* Real timer semantics are implemented by the sim backend (st_sim.py). *)
Q := FALSE;
ET := T#0S;"""),
}


def ensure_timer_stubs(app):
    """创建 TON/TOF/TP 编译桩（已存在则跳过）。"""
    made = []
    existing = set()
    try:
        for o in app.get_children(True):
            try:
                existing.add(str(o.get_name()).upper())
            except Exception:
                pass
    except Exception:
        pass
    for name, (decl, impl) in TIMER_STUBS.items():
        if name in existing:
            continue
        try:
            stub = app.create_pou(name, PouType.FunctionBlock,
                                  ImplementationLanguages.st)
            stub.textual_declaration.replace(decl)
            stub.textual_implementation.replace(impl)
            made.append(name)
        except Exception:
            pass
    return made


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

        # Standard Library：可用则引用真库；不可用回退到 TON/TOF/TP 编译桩
        std_ok = ensure_standard_library(proj)
        result["steps"]["standard_library"] = "referenced" if std_ok else "not found"
        if not std_ok:
            result["steps"]["timer_stubs"] = ensure_timer_stubs(app)
        else:
            # 旧模板里可能带着桩，清掉避免与真库的 TON/TOF/TP 重名
            removed = []
            for obj in proj.get_children(True):
                try:
                    nm = str(obj.get_name())
                except Exception:
                    continue
                if nm in TIMER_STUBS:
                    try:
                        obj.delete()
                        removed.append(nm)
                    except Exception:
                        pass
            result["steps"]["timer_stubs_removed"] = removed

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
