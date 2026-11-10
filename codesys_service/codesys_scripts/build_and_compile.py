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
  6. 最关键：POU 必须挂到任务的调用列表，否则 build() 会跳过，任何错误都报 0
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


def log(msg):
    try:
        print("[codesys-build] %s" % msg)
    except Exception:
        pass


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


def split_pou(text):
    """拆成 (声明段, 实现段, 原 POU 名)。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    header_idx = None
    for i, ln in enumerate(lines):
        if ln.strip().upper().startswith(("PROGRAM", "FUNCTION_BLOCK", "FUNCTION")):
            header_idx = i
            break
    if header_idx is None:
        return "", text, None

    m = re.match(r"\s*(PROGRAM|FUNCTION_BLOCK|FUNCTION)\s+([A-Za-z_]\w*)",
                 lines[header_idx], re.IGNORECASE)
    orig_name = m.group(2) if m else None

    var_depth = 0
    seen_var = False
    body_idx = len(lines)
    for i in range(header_idx + 1, len(lines)):
        s = lines[i].strip()
        if not s:
            continue
        first = s.upper().split()[0].rstrip(";(")
        if first.startswith("VAR"):
            var_depth += 1
            seen_var = True
            continue
        if first == "END_VAR":
            var_depth = max(0, var_depth - 1)
            continue
        if var_depth > 0:
            continue
        if seen_var:
            body_idx = i
            break

    decl = "\n".join(lines[header_idx:body_idx]).strip()
    impl = "\n".join(lines[body_idx:]).strip()
    for tail in ("END_PROGRAM", "END_FUNCTION_BLOCK", "END_FUNCTION"):
        if impl.upper().rstrip().endswith(tail):
            impl = impl[: impl.upper().rfind(tail)].rstrip()
    return decl, impl, orig_name


def rename_decl(decl, new_name):
    return re.sub(r"^(\s*(?:PROGRAM|FUNCTION_BLOCK|FUNCTION)\s+)([A-Za-z_]\w*)",
                  lambda m: m.group(1) + new_name, decl, count=1, flags=re.IGNORECASE)


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


def find_by_name(holder, name, need_text=False):
    try:
        for obj in holder.get_children(True):
            try:
                if str(obj.get_name()) != name:
                    continue
                if need_text and not hasattr(obj, "textual_declaration"):
                    continue
                return obj
            except Exception:
                continue
    except Exception:
        pass
    return None


def ensure_pou(app, name):
    pou = find_by_name(app, name, need_text=True)
    if pou is not None:
        return pou, "existing"
    ptype = getattr(PouType, "Program", None)
    lang = getattr(ImplementationLanguages, "st", None)
    attempts = []
    if ptype is not None and lang is not None:
        attempts.append(lambda: app.create_pou(name, ptype, lang))
    if ptype is not None:
        attempts.append(lambda: app.create_pou(name, ptype))
    attempts.append(lambda: app.create_pou(name))
    for call in attempts:
        try:
            return call(), "created"
        except Exception as exc:
            log("create_pou failed: %s" % exc)
    raise RuntimeError("POU %s not found and cannot be created" % name)


def ensure_task(proj, app, pou_name):
    """确保任务存在并把 POU 加进调用列表——否则编译不检查代码。"""
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


def compile_one(proj, app, system, job):
    t0 = time.time()
    item = {"name": job.get("name") or job.get("pou"), "pou": job.get("pou"),
            "ok": False, "errors": [], "warnings": [], "api": {}}

    text = read_text(job["st"])
    decl, impl, orig_name = split_pou(text)
    if not impl.strip():
        item["errors"].append({"level": "error",
                               "text": "no implementation body in ST file"})
        item["duration_s"] = round(time.time() - t0, 2)
        return item

    pou, how = ensure_pou(app, job["pou"])
    item["api"]["pou"] = how
    item["api"]["orig_name"] = orig_name
    item["api"]["decl"] = set_text(pou.textual_declaration, rename_decl(decl, job["pou"]))
    item["api"]["impl"] = set_text(pou.textual_implementation, impl)
    item["api"]["task"] = ensure_task(proj, app, job["pou"])

    try:
        for cat in system.get_message_categories():
            system.clear_messages(cat)
    except Exception as exc:
        log("clear_messages failed: %s" % exc)

    ret = app.build()
    item["api"]["build"] = "app.build()"
    item["build_returned"] = repr(ret)

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

        for job in args["jobs"]:
            log("compiling %s -> %s" % (job["st"], job.get("pou")))
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
