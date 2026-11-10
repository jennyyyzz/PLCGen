# -*- coding: utf-8 -*-
"""在 CODESYS ScriptEngine 内运行：导入 ST -> 编译 -> 收消息 -> 写 JSON。

由 codesys_compile.py 调用（一个进程编一个文件，保证互不干扰）。

实测要点（CODESYS V3.5 SP22 Patch 4 / ScriptEngine = IronPython 2.7）：
  1. 源码里的中文字面量会乱码（IronPython 按 ANSI 读源码），运行期提示一律英文
  2. 内置 open() 不支持 encoding，统一用 io.open
  3. app.find() 找不到 POU，只能遍历 get_children(True)
  4. system.get_messages() 不传 category 返回空；要逐 category 取
  5. 取回来的消息是**纯字符串**，没有 severity 字段
     → 用「编译完成--N错误,M警告」判定，其余非进度行当错误文本
  6. POU 必须能被任务触达，否则 build() 直接跳过（甚至报「此应用程序是最新的」），
     任何错误都会被吞成 0 错误。所以：
       - PROGRAM 直接加进 MainTask 调用列表
       - FUNCTION_BLOCK / FUNCTION 不能挂任务（FB 必须先实例化，直接挂会报
         「功能块'xxx' 访问时必须被实例化」），改为生成一个 wrapper PROGRAM
         去实例化并调用它，再把 wrapper 挂进 MainTask
  7. build() 是增量的，改完代码可能仍报「此应用程序是最新的」；一律用 rebuild()
     触发全量重建，没有该 API 时退化为 clean() + build()
"""
import io
import json
import os
import re
import sys
import time
import traceback

NOISE = re.compile(r"(开始构建|代码典型化|编译完成|生成代码|正在准备|正在编译|"
                   r"其他代码检查|附加代码检查|离线帮助|\[codesys-build\])")
SUMMARY = re.compile(r"(\d+)\s*错误\s*[,，]\s*(\d+)\s*警告")

# ST 头关键字 -> CODESYS PouType 成员名
POU_KIND = {
    "PROGRAM": "Program",
    "FUNCTION_BLOCK": "FunctionBlock",
    "FUNCTION": "Function",
}
HEADER_RE = re.compile(
    r"^\s*(PROGRAM|FUNCTION_BLOCK|FUNCTION)\s+([A-Za-z_]\w*)\s*(?::\s*([^;]*))?",
    re.IGNORECASE)

# 模板工程里自带的 PROGRAM，FB/FUNCTION 借用它当 wrapper
WRAPPER_NAME = "PLC_PRG"
WRAPPER_ALT = "PLC_PRG_WRAP"


def log(msg):
    try:
        print("[codesys-build] %s" % msg)
    except Exception:
        pass


TIMER_STUB_NAMES = ("TON", "TOF", "TP")
STUB_MARKER = "Compile-only stub provided by the toolchain service"


def remove_timer_stubs(app):
    """Standard 库已生效时删掉旧的 TON/TOF/TP 编译桩，避免遮蔽真库符号。"""
    removed = []
    if app is None:
        return removed
    for obj in app.get_children(True):
        try:
            nm = str(obj.get_name()).upper()
        except Exception:
            continue
        if nm not in TIMER_STUB_NAMES:
            continue
        try:
            impl = str(obj.textual_implementation.text)
        except Exception:
            impl = ""
        if STUB_MARKER not in impl:
            continue
        try:
            obj.delete()
            removed.append(nm)
        except Exception:
            pass
    return removed


def ensure_standard_library(proj, app=None):
    """在工程库管理器里引用真 Standard Library（TON/TOF/TP/LEN/MID 等）。

    noUI 模式下 `add_library("Standard, * (System)")` 只写引用不装载，
    编译仍报「未知的类型: 'TON'」；正解是从 librarymanager 仓库拿到
    真实库对象后 add_placeholder，占位符在 build 时解析。
    返回 {"status": already|added|missing|..., "version": ..., "removed_stubs": [...]}。
    库可用时会顺手删掉模板里遗留的 TON/TOF/TP 编译桩，避免同名遮蔽真库。
    """
    libman = None
    for obj in proj.get_children(True):
        try:
            if getattr(obj, "is_libman", False):
                libman = obj
                break
        except Exception:
            pass
    if libman is None:
        return {"status": "no libman", "removed_stubs": []}
    # 已引用过就跳过（注意不能用子串：#IoStandard 也含 "Standard"）
    try:
        for ref in libman.get_libraries():
            try:
                nm = str(ref).lstrip("#").split(",")[0].strip()
                if nm == "Standard":
                    return {"status": "already",
                            "removed_stubs": remove_timer_stubs(app)}
            except Exception:
                pass
    except Exception:
        pass
    lmg = globals().get("librarymanager")
    if lmg is None:
        return {"status": "no librarymanager", "removed_stubs": []}
    try:
        for repo in lmg.repositories:
            for lib in lmg.get_all_libraries(repo):
                try:
                    if str(lib.title) == "Standard":
                        libman.add_placeholder("Standard", lib)
                        return {"status": "added",
                                "version": str(getattr(lib, "displayname", "")),
                                "removed_stubs": remove_timer_stubs(app)}
                except Exception:
                    continue
    except Exception:
        pass
    return {"status": "missing", "removed_stubs": []}


def load_args():
    for a in reversed(sys.argv[1:]):
        a = str(a).strip().strip('"')
        if not a:
            continue
        if a.startswith("{"):
            return json.loads(a)
        if os.path.isfile(a):
            fh = io.open(a, "r", encoding="utf-8")
            try:
                return json.load(fh)
            finally:
                fh.close()
    raise SystemExit("no script args found")


def read_text(path):
    fh = io.open(path, "r", encoding="utf-8-sig", errors="replace")
    try:
        return fh.read()
    finally:
        fh.close()


def write_json(path, data):
    fh = io.open(path, "w", encoding="utf-8")
    try:
        fh.write(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    finally:
        fh.close()


# ------------------------------------------------------------------ ST 解析

def split_pou(text):
    """拆成 (声明段, 实现段, 头部信息)。

    头部信息 = {kind_raw, kind, name, return_type}；找不到 POU 头时返回空 dict。
    kind 是 CODESYS PouType 的成员名：Program / FunctionBlock / Function。
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    header_idx = None
    for i, ln in enumerate(lines):
        if HEADER_RE.match(ln):
            header_idx = i
            break
    if header_idx is None:
        return "", text, {}

    m = HEADER_RE.match(lines[header_idx])
    raw = m.group(1).upper()
    info = {
        "kind_raw": raw,
        "kind": POU_KIND.get(raw),
        "name": m.group(2),
        "return_type": (m.group(3) or "").strip() or None,
    }

    # 实现段从最后一个顶层 END_VAR 之后的第一条语句开始；没有 VAR 块就直接跟在头后面
    body_idx = None
    depth = 0
    for i in range(header_idx + 1, len(lines)):
        s = lines[i].strip()
        if not s:
            continue
        first = s.upper().split()[0].rstrip(";(")
        if first.startswith("VAR"):
            depth += 1
            continue
        if first == "END_VAR":
            depth = max(0, depth - 1)
            continue
        if depth > 0:
            continue
        body_idx = i
        break
    if body_idx is None:
        body_idx = len(lines)

    decl = "\n".join(lines[header_idx:body_idx]).strip()
    impl = "\n".join(lines[body_idx:]).strip()
    for tail in ("END_PROGRAM", "END_FUNCTION_BLOCK", "END_FUNCTION"):
        if impl.upper().rstrip().endswith(tail):
            impl = impl[: impl.upper().rfind(tail)].rstrip()
    return decl, impl, info


def rename_decl(decl, new_name):
    """把声明段首行的 POU 名换掉（保留 PROGRAM/FUNCTION_BLOCK/FUNCTION 与返回类型）。"""
    return re.sub(r"^(\s*(?:PROGRAM|FUNCTION_BLOCK|FUNCTION)\s+)([A-Za-z_]\w*)",
                  lambda m: m.group(1) + new_name, decl, count=1, flags=re.IGNORECASE)


def split_duts(text):
    """把 TYPE ... END_TYPE 块从源码里拆出来（问题③）。

    CODESYS 里 TYPE...END_TYPE 必须是独立的 DUT 对象，不能混在 POU 正文里
    （否则报「未知的类型: 'ST_Pump'」「无效的赋值目标」）。
    返回 (去掉 DUT 段后的剩余源码, [(类型名, 完整块文本)])。
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    duts = []
    rest = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        stripped = ln.strip()
        if (re.match(r"^TYPE\s+[A-Za-z_]\w*\s*:", stripped, re.IGNORECASE)
                and not stripped.startswith(("//", "(*"))):
            name = re.match(r"^TYPE\s+([A-Za-z_]\w*)", stripped,
                            re.IGNORECASE).group(1)
            block = [ln]
            i += 1
            while i < n:
                s = lines[i].strip().upper()
                block.append(lines[i])
                i += 1
                if s.startswith("END_TYPE"):
                    break
            duts.append((name, "\n".join(block).strip()))
        else:
            rest.append(ln)
            i += 1
    return "\n".join(rest), duts


def ensure_dut(app, name, text):
    """创建/复用 DUT 对象并写入 TYPE...END_TYPE 全文。"""
    dut = find_by_name(app, name, need_text=True)
    how = "existing"
    if dut is None:
        dut = app.create_dut(name)
        how = "created"
    if dut is None:
        raise RuntimeError("create_dut(%s) returned None" % name)
    set_text(dut.textual_declaration, text)
    return how


def var_block_entries(decl, block_name):
    """从声明段里取指定 VAR 块的 [(变量名, 类型)]。block_name 如 VAR_IN_OUT。"""
    entries = []
    inside = False
    opener = re.compile(r"^%s\b" % block_name.upper())
    for ln in decl.split("\n"):
        s = ln.strip()
        if not s:
            continue
        u = s.upper()
        if opener.match(u):
            inside = True
            continue
        if inside and u.startswith("END_VAR"):
            inside = False
            continue
        if not inside or s.startswith(("(*", "//")) or ":" not in s:
            continue
        nm, ty = s.split(":", 1)
        nm = nm.strip()
        if not re.match(r"^[A-Za-z_]\w*$", nm):
            continue
        ty = ty.split(":=")[0].strip().rstrip(";").strip()
        if ty:
            entries.append((nm, ty))
    return entries


# ------------------------------------------------------------------ CODESYS 对象

def set_text(obj, text):
    tried = []
    for attr in ("replace", "set_text"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                fn(text)
                return attr
            except Exception as exc:
                tried.append("%s: %s" % (attr, exc))
    try:
        obj.text = text
        return "text="
    except Exception as exc:
        tried.append("text=: %s" % exc)
    raise RuntimeError("cannot set text: " + "; ".join(tried))


def find_by_name(holder, name, need_text=False):
    try:
        for obj in holder.get_children(True):
            try:
                if str(obj.get_name()).upper() != str(name).upper():
                    continue
                if need_text and not hasattr(obj, "textual_declaration"):
                    continue
                return obj
            except Exception:
                continue
    except Exception:
        pass
    return None


def kind_of(pou):
    """从声明文本首行判断 POU 类型。

    ScriptObject 上没有 pou_type 属性（实测 AttributeError），只能读
    textual_declaration.text（ScriptTextDocument.text）再解析头关键字。
    """
    try:
        raw = []
        for attr in ("textual_declaration", "textual_implementation"):
            try:
                raw.append(str(getattr(pou, attr).text))
            except Exception:
                pass
        text = raw[0] if raw else ""
    except Exception:
        return None
    for ln in text.replace("\r\n", "\n").split("\n"):
        if not ln.strip():
            continue
        m = HEADER_RE.match(ln)
        return POU_KIND.get(m.group(1).upper()) if m else None
    return None


def create_pou_with_kind(app, name, kind, return_type=None):
    """按 POU 类型创建对象。FUNCTION 必须带 return_type，否则 CODESYS 直接报参数错误。"""
    ptype = getattr(PouType, kind, None)
    lang = getattr(ImplementationLanguages, "st", None)
    attempts = []
    if ptype is not None:
        if kind == "Function" and return_type:
            attempts.append(("create_pou(name, type, lang, return_type)",
                             lambda: app.create_pou(name, ptype, lang, return_type)))
            attempts.append(("create_pou(name, type, return_type)",
                             lambda: app.create_pou(name, ptype, return_type)))
        if lang is not None:
            attempts.append(("create_pou(name, type, lang)",
                             lambda: app.create_pou(name, ptype, lang)))
        attempts.append(("create_pou(name, type)",
                         lambda: app.create_pou(name, ptype)))
    attempts.append(("create_pou(name)", lambda: app.create_pou(name)))

    errors = []
    for label, call in attempts:
        try:
            obj = call()
        except Exception as exc:
            errors.append("%s -> %s" % (label, exc))
            continue
        if obj is None:
            errors.append("%s -> returned None" % label)
            continue
        got = kind_of(obj)
        if got and got != kind:
            # 建错了类型（比如裸 create_pou 默认建 Program），删掉重试
            errors.append("%s -> created as %s" % (label, got))
            try:
                obj.remove()
            except Exception:
                pass
            continue
        return obj, label
    raise RuntimeError("cannot create %s POU '%s' (%s)"
                       % (kind, name, "; ".join(errors)[:400]))


def ensure_pou(app, name, kind, return_type=None):
    """同名 POU 存在且类型一致就复用；类型不一致则删掉重建。

    复用是必须的：模板里的 PLC_PRG 已经挂在 MainTask 上，删了得重新挂。
    """
    pou = find_by_name(app, name, need_text=True)
    how = "existing"
    if pou is not None:
        cur = kind_of(pou)
        if cur and cur != kind:
            try:
                pou.remove()
            except Exception as exc:
                raise RuntimeError(
                    "POU '%s' already exists as %s and cannot be replaced by %s: %s"
                    % (name, cur, kind, exc))
            pou = None
            how = "replaced(%s->%s)" % (cur, kind)

    if pou is None:
        pou, label = create_pou_with_kind(app, name, kind, return_type)
        how = "created" if how == "existing" else how + "/created"
        got = kind_of(pou)
        if got and got != kind:
            raise RuntimeError("created POU '%s' as %s but %s was requested"
                               % (name, got, kind))
        log("created %s POU %s via %s" % (kind, name, label))
    return pou, how


def ensure_task(proj, app, pou_name):
    """确保任务存在并把 POU 加进调用列表——否则编译不检查代码。

    只对 PROGRAM 调用：FB/FUNCTION 不能直接挂任务。
    """
    task = find_by_name(proj, "MainTask")
    info = "existing"
    if task is None:
        tc = app.create_task_configuration()
        task = tc.create_task("MainTask")
        info = "created"
    try:
        task.pous.add(pou_name)
    except Exception as exc:
        log("task.pous.add(%s) failed: %s" % (pou_name, exc))
    return info


def drop_from_task(proj, pou_name):
    """把某个 POU 从任务调用列表里摘掉（FB 顶着模板 PROGRAM 的名字时要用）。"""
    task = find_by_name(proj, "MainTask")
    if task is None:
        return False
    try:
        task.pous.remove(pou_name)
        return True
    except Exception as exc:
        log("task.pous.remove(%s) skipped: %s" % (pou_name, exc))
        return False


def prepare_wrapper(app, proj, target_name, kind, decl, return_type):
    """给 FB / FUNCTION 生成一个 PROGRAM wrapper，让 build() 真的编译它。

    FB  : PROGRAM PLC_PRG  VAR wrapInst : FB_Q03; END_VAR   wrapInst();
    FUNC: PROGRAM PLC_PRG  VAR wrapResult : INT;  END_VAR   wrapResult := ADD2();
    VAR_IN_OUT 必须传实参，否则报「输入输出参数未赋值」，所以一并生成占位变量。
    """
    wname = WRAPPER_NAME
    if target_name.upper() == WRAPPER_NAME.upper():
        wname = WRAPPER_ALT

    w = find_by_name(app, wname, need_text=True)
    if w is not None and kind_of(w) != "Program":
        w = None
    how = "existing"
    if w is None and wname != WRAPPER_ALT:
        alt = find_by_name(app, WRAPPER_ALT, need_text=True)
        if alt is not None and kind_of(alt) == "Program":
            w, wname = alt, WRAPPER_ALT
    if w is None:
        w, _ = create_pou_with_kind(app, wname, "Program")
        how = "created"

    extra = ""
    args = []
    for i, (nm, ty) in enumerate(var_block_entries(decl, "VAR_IN_OUT")):
        var = "wrapIo%d" % i
        extra += "    %s : %s;\n" % (var, ty)
        args.append("%s := %s" % (nm, var))

    if kind == "FunctionBlock":
        wdecl = "PROGRAM %s\nVAR\n    wrapInst : %s;\n%sEND_VAR" % (
            wname, target_name, extra)
        wimpl = "wrapInst(%s);" % ", ".join(args)
    elif kind == "Function":
        if not return_type:
            raise RuntimeError("FUNCTION '%s' has no return type in its header"
                               % target_name)
        for i, (nm, ty) in enumerate(var_block_entries(decl, "VAR_INPUT")):
            var = "wrapIn%d" % i
            extra += "    %s : %s;\n" % (var, ty)
            args.append("%s := %s" % (nm, var))
        wdecl = "PROGRAM %s\nVAR\n    wrapResult : %s;\n%sEND_VAR" % (
            wname, return_type, extra)
        wimpl = "wrapResult := %s(%s);" % (target_name, ", ".join(args))
    else:
        raise RuntimeError("no wrapper needed for %s" % kind)

    set_text(w.textual_declaration, wdecl)
    set_text(w.textual_implementation, wimpl)
    return {"program": wname, "task": ensure_task(proj, app, wname),
            "how": how, "decl": wdecl, "impl": wimpl}


def run_build(app):
    """优先全量重建：增量 build() 会拿「此应用程序是最新的」把错误吞掉。"""
    fn = getattr(app, "rebuild", None)
    if callable(fn):
        try:
            fn()
            return "app.rebuild()"
        except Exception as exc:
            log("rebuild failed, fallback to clean+build: %s" % exc)
    clean = getattr(app, "clean", None)
    if callable(clean):
        try:
            clean()
        except Exception as exc:
            log("clean failed: %s" % exc)
    app.build()
    return "app.build()"


def build_messages(system):
    """返回 (错误数, 警告数, 错误文本列表)。"""
    errs, warns, texts = 0, 0, []
    for cat in system.get_message_categories():
        try:
            msgs = [str(m) for m in system.get_messages(cat)]
        except Exception:
            continue
        for s in msgs:
            m = SUMMARY.search(s)
            if m:
                errs = int(m.group(1))
                warns = int(m.group(2))
                continue
            if NOISE.search(s) or s.startswith("------"):
                continue
            texts.append(s[:300])
    return errs, warns, texts


def compile_one(proj, app, system, job):
    t0 = time.time()
    item = {"name": job.get("name") or job.get("pou"), "pou": None,
            "ok": False, "errors": [], "warnings": [], "api": {}}

    text = read_text(job["st"])
    # TYPE...END_TYPE 先拆出来建成独立 DUT 对象（CODESYS 不允许混进 POU 正文）
    text, dut_blocks = split_duts(text)
    decl, impl, info = split_pou(text)
    if dut_blocks:
        item["api"]["duts"] = []
        for dname, dtext in dut_blocks:
            how = ensure_dut(app, dname, dtext)
            item["api"]["duts"].append({"name": dname, "how": how})
            log("DUT %s (%s)" % (dname, how))
    kind = info.get("kind")
    orig = info.get("name")
    if not kind:
        item["errors"].append({
            "level": "error",
            "text": "no PROGRAM / FUNCTION_BLOCK / FUNCTION header found in ST file"})
        item["duration_s"] = round(time.time() - t0, 2)
        return item

    # pou 未指定时沿用代码里声明的名字，避免把 FUNCTION_BLOCK FB_Q03 硬塞进 PLC_PRG
    target = job.get("pou") or orig
    # PLC_PRG 是模板里已经挂在 MainTask 上的 PROGRAM，FB/FUNCTION 不能占这个名：
    # 占了就得把它从任务列表摘掉（ScriptEngine 没提供删除接口），编译会报
    # 「功能块'PLC_PRG' 访问时必须被实例化」。换个名字，wrapper 继续用 PLC_PRG。
    if kind != "Program" and str(target).upper() == WRAPPER_NAME.upper():
        target = "%s_FB" % (orig or target)
    item["pou"] = target
    item["api"].update({"kind": kind, "orig_name": orig,
                        "requested_pou": job.get("pou"),
                        "renamed": bool(orig and orig != target)})

    pou, how = ensure_pou(app, target, kind, info.get("return_type"))
    item["api"]["pou"] = how
    item["api"]["decl"] = set_text(pou.textual_declaration, rename_decl(decl, target))
    item["api"]["impl"] = set_text(pou.textual_implementation, impl)

    if kind == "Program":
        item["api"]["task"] = ensure_task(proj, app, target)
        item["api"]["entry"] = target
    else:
        # FB/FUNCTION 如果顶掉了模板里的 PROGRAM 同名对象，任务列表里还留着旧名字
        drop_from_task(proj, target)
        wrap = prepare_wrapper(app, proj, target, kind, decl,
                               info.get("return_type"))
        item["api"]["task"] = wrap["task"]
        item["api"]["entry"] = wrap["program"]
        item["api"]["wrapper"] = {"program": wrap["program"],
                                  "how": wrap["how"],
                                  "decl": wrap["decl"],
                                  "impl": wrap["impl"]}

    try:
        for cat in system.get_message_categories():
            system.clear_messages(cat)
    except Exception as exc:
        log("clear_messages failed: %s" % exc)

    item["api"]["build"] = run_build(app)

    errs, warns, texts = build_messages(system)
    item["api"]["messages"] = "system.get_messages(category)"
    item["counts"] = {"errors": errs, "warnings": warns}
    for s in texts:
        item["errors"].append({"level": "error", "text": s})
    item["ok"] = (errs == 0 and not item["errors"])
    if item["ok"]:
        item["errors"] = []
    item["duration_s"] = round(time.time() - t0, 2)
    return item


def main():
    args = load_args()
    out_path = args["out"]
    result = {"ok": False, "project": args.get("project"), "items": [],
              "api": {}, "fatal": None}

    project_path = args.get("work_project") or args["project"]
    try:
        src = args["project"]
        if args.get("work_project") and os.path.abspath(src) != os.path.abspath(project_path):
            import shutil
            shutil.copyfile(src, project_path)

        proj = projects.open(project_path)
        if proj is None:
            proj = getattr(projects, "primary", None)
        if proj is None:
            raise RuntimeError("cannot open project: %s" % project_path)
        result["api"]["open"] = "projects.open(path)"

        app = proj.active_application
        if app is None:
            raise RuntimeError("no Application object in template")
        result["api"]["application"] = "active_application"
        system = globals().get("system")

        # Standard Library：noUI 下 add_library 字符串引用不装载，必须用
        # 仓库对象 add_placeholder；每次会话 ensure 一次（幂等）。
        try:
            result["api"]["stdlib"] = ensure_standard_library(proj, app)
            log("stdlib: %s" % result["api"]["stdlib"])
        except Exception:
            result["api"]["stdlib"] = {"status": "FAIL",
                                       "error": traceback.format_exc()}

        for job in args["jobs"]:
            log("compiling %s -> %s" % (job["st"], job.get("pou") or "<auto>"))
            try:
                result["items"].append(compile_one(proj, app, system, job))
            except Exception:
                result["items"].append({
                    "name": job.get("name") or job.get("pou"),
                    "pou": job.get("pou"),
                    "ok": False,
                    "errors": [{"level": "error", "text": traceback.format_exc()}],
                    "warnings": [],
                    "api": {},
                })

        try:
            proj.close()
        except Exception:
            pass
        result["ok"] = all(i["ok"] for i in result["items"]) if result["items"] else False
    except Exception:
        result["fatal"] = traceback.format_exc()
        result["ok"] = False
    finally:
        write_json(out_path, result)
        log("result -> %s" % out_path)


main()
