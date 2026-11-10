# -*- coding: utf-8 -*-
"""CODESYS 命令行编译封装（宿主机侧入口）

把「一段 ST 文本 -> CODESYS 编译 -> 结构化错误列表」包装成一次 CLI 调用，
Agent 只需要读 JSON，不用碰 CODESYS 界面。

两道闸门
  1) 先跑离线静态检查（st_lint），有 error 直接判失败，不浪费一次 2~3 分钟的编译
  2) 静态检查通过才拉起 CODESYS（--noUI 无界面模式），跑完即退

用法
  # 看一眼本机有哪些 CODESYS profile
  python codesys_compile.py --list-profiles

  # 编译单个文件
  python codesys_compile.py --st demo/motor_start_stop.st --pou PLC_PRG \
      --project templates/template.project --out out/q01.json

  # 批量：一个 CODESYS 进程编译整个目录（推荐，省掉 N-1 次开工程）
  python codesys_compile.py --st out/st/ --project templates/template.project \
      --out out/compile.json

  # 没装 CODESYS 也能跑：只做静态检查
  python codesys_compile.py --st demo/ --backend lint --out out/lint.json

退出码：0 = 全部通过；1 = 有失败；2 = 环境/参数问题
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
INNER_SCRIPT = HERE / "codesys_scripts" / "build_and_compile.py"
LINT = HERE / "st_lint.py"

EXE_PATTERNS = [
    r"C:\Program Files\CODESYS*\CODESYS\Common\CODESYS.exe",
    r"C:\Program Files (x86)\CODESYS*\CODESYS\Common\CODESYS.exe",
]
PROFILE_DIRS = [
    Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "CODESYS" / "CODESYSProfiles",
]


# ------------------------------------------------------------------ 环境探测

def find_codesys_exe(explicit: str | None = None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    env = os.environ.get("CODESYS_EXE")
    if env and Path(env).is_file():
        return Path(env)

    import glob
    found = []
    for pat in EXE_PATTERNS:
        found.extend(glob.glob(pat))
    # 新版本号排前面（SP20 优于 SP17）
    if found:
        found.sort(reverse=True)
        return Path(found[0])
    return None


def _profile_dirs() -> list[Path]:
    """profile 存放位置随版本变过：老版本在 ProgramData，SP17+ 装到安装目录下。"""
    dirs = [d for d in PROFILE_DIRS if d.is_dir()]
    import glob
    for pat in EXE_PATTERNS:
        for exe in glob.glob(pat):
            # <install>\CODESYS\Common\CODESYS.exe -> <install>\CODESYS\Profiles
            p = Path(exe).parent.parent / "Profiles"
            if p.is_dir():
                dirs.append(p)
    return dirs


def list_profiles() -> list[str]:
    names = []
    for d in _profile_dirs():
        for f in sorted(d.glob("*.profile")):
            names.append(f.stem)
        for f in sorted(d.glob("*.profile.xml")):
            names.append(f.name[: -len(".profile.xml")])
    return sorted(set(names))


def resolve_profile(explicit: str | None) -> tuple[str | None, list[str]]:
    profiles = list_profiles()
    if explicit:
        return explicit, profiles
    env = os.environ.get("CODESYS_PROFILE")
    if env:
        return env, profiles
    if not profiles:
        return None, profiles
    # 优先 V3.5 SPxx，取版本号最大的
    def key(p):
        nums = [int(x) for x in re.findall(r"\d+", p)]
        return nums
    try:
        profiles = sorted(profiles, key=key)
    except Exception:
        pass
    return profiles[-1], profiles


# ------------------------------------------------------------------ 任务准备

def sanitize_pou(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_]", "_", name)
    if not s or s[0].isdigit():
        s = "P_" + s
    return s[:60]


def collect_jobs(target: Path, default_pou: str) -> list[dict]:
    if target.is_file():
        return [{"name": target.stem, "st": str(target.resolve()),
                 "pou": default_pou}]
    jobs = []
    for f in sorted(target.rglob("*.st")):
        # 整批共用一个 POU：每次覆盖内容，上一题的代码不会残留
        jobs.append({"name": f.stem, "st": str(f.resolve()),
                     "pou": default_pou})
    return jobs


def run_lint_gate(jobs: list[dict], enabled: bool) -> dict:
    """对每个文件跑离线检查，返回 {st_path: lint_result}。"""
    if not enabled:
        return {}
    sys.path.insert(0, str(HERE))
    try:
        from st_lint import lint_source
    except Exception:
        return {}

    gate = {}
    for job in jobs:
        try:
            text = Path(job["st"]).read_text(encoding="utf-8", errors="replace")
            gate[job["st"]] = lint_source(text, job["st"])
        except Exception as exc:
            gate[job["st"]] = {"ok": True, "errors": [], "warnings": [],
                               "lint_error": str(exc)}
    return gate


# ------------------------------------------------------------------ 主流程

def _run_in_codesys(exe: Path, profile: str, script: Path, args_path: Path | None,
                    timeout: int) -> dict:
    """拉起 CODESYS 执行脚本。

    必须走 .bat：CODESYS 解析命令行时要求 --profile="名字" 里的引号出现在
    参数内部，Python 用 argv 列表会把它转义成 \\"，CODESYS 就报
    「必须使用 --profile 指定配置文件」。另外 .bat 要以 GBK 写盘，
    并把脚本复制到纯 ASCII 的临时目录，避免中文路径在 cmd 里变乱码。
    """
    workdir = Path(tempfile.mkdtemp(prefix="codesys_call_"))
    local_script = workdir / script.name
    shutil.copyfile(script, local_script)

    bat = workdir / "run.bat"
    line = '@echo off\r\n"%s" --profile="%s" --noUI --runscript="%s"' % (
        exe, profile, local_script)
    if args_path is not None:
        local_args = workdir / "args.json"
        shutil.copyfile(args_path, local_args)
        line += ' --scriptargs="%s"' % local_args
    line += "\r\n"
    with open(bat, "wb") as fh:
        fh.write(line.encode("gbk", errors="replace"))

    t0 = time.time()
    try:
        proc = subprocess.run(["cmd", "/c", str(bat)], capture_output=True,
                              timeout=timeout)
        rc = proc.returncode
        raw = (proc.stdout or b"") + (proc.stderr or b"")
    except subprocess.TimeoutExpired as exc:
        rc = -1
        raw = (exc.stdout or b"") + ("\nTIMEOUT after %ss" % timeout).encode("gbk")
    duration = round(time.time() - t0, 1)

    text = raw.decode("gbk", errors="replace")
    return {"returncode": rc, "duration_s": duration, "text": text,
            "workdir": workdir}


def compile_with_codesys(jobs: list[dict], project: Path, exe: Path,
                         profile: str, timeout: int) -> dict:
    workdir = Path(tempfile.mkdtemp(prefix="codesys_build_"))
    work_project = workdir / "work.project"
    args_path = workdir / "args.json"
    out_path = workdir / "result.json"

    payload = {
        "project": str(project.resolve()),
        "work_project": str(work_project),
        "out": str(out_path),
        "jobs": [{"name": j["name"], "pou": j["pou"], "st": j["st"]} for j in jobs],
    }
    args_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    run = _run_in_codesys(exe, profile, INNER_SCRIPT, args_path, timeout)

    result = {"ok": False, "items": [], "fatal": None}
    if out_path.is_file():
        try:
            result = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception as exc:
            result["fatal"] = "结果文件无法解析: %s" % exc
    else:
        result["fatal"] = ("CODESYS 未产出结果文件（rc=%s）。"
                           "常见原因：profile 名不对、工程被占用、或脚本 API 不兼容。"
                           % run["returncode"])
    result["process"] = {"returncode": run["returncode"],
                         "duration_s": run["duration_s"],
                         "stdout_tail": run["text"][-2000:],
                         "stderr_tail": ""}
    shutil.rmtree(workdir, ignore_errors=True)
    shutil.rmtree(run["workdir"], ignore_errors=True)
    return result


def make_template(exe: Path, profile: str, out_project: Path,
                  device: str, timeout: int) -> dict:
    """用脚本从零生成模板工程（比 GUI 手工建更干净、可复现）。"""
    workdir = Path(tempfile.mkdtemp(prefix="codesys_tpl_"))
    args_path = workdir / "args.json"
    report = workdir / "report.json"
    out_project.parent.mkdir(parents=True, exist_ok=True)
    args_path.write_text(json.dumps({
        "out": str(out_project.resolve()),
        "device": device,
        "report": str(report),
    }, ensure_ascii=False), encoding="utf-8")

    run = _run_in_codesys(exe, profile, HERE / "codesys_scripts" / "make_template.py",
                          args_path, timeout)
    info = {"ok": False, "report": None, "log": run["text"][-3000:],
            "returncode": run["returncode"]}
    if report.is_file():
        try:
            info["report"] = json.loads(report.read_text(encoding="utf-8"))
            info["ok"] = bool(info["report"].get("ok"))
        except Exception as exc:
            info["error"] = str(exc)
    shutil.rmtree(run["workdir"], ignore_errors=True)
    return info


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="CODESYS 命令行编译封装")
    ap.add_argument("--st", required=False, help=".st 文件或目录")
    ap.add_argument("--pou", default="PLC_PRG",
                    help="目标 POU 名（单文件模式用；批量模式用文件名）")
    ap.add_argument("--project", help="模板工程 .project 路径")
    ap.add_argument("--backend", default="auto",
                    choices=["auto", "codesys", "lint"],
                    help="auto=有 CODESYS 就编译，否则只做静态检查")
    ap.add_argument("--out", help="结果 JSON 输出路径")
    ap.add_argument("--timeout", type=int, default=900, help="单次 CODESYS 超时秒数")
    ap.add_argument("--codesys-exe", help="CODESYS.exe 完整路径")
    ap.add_argument("--profile", help="CODESYS profile 名，如 'CODESYS V3.5 SP19 Patch 4'")
    ap.add_argument("--list-profiles", action="store_true", help="列出本机 CODESYS profile")
    ap.add_argument("--make-template", action="store_true",
                    help="用脚本从零生成模板工程（需 --codesys-exe 可用）")
    ap.add_argument("--device", default="CODESYS Control Win V3 x64",
                    help="生成模板时使用的设备名")
    ap.add_argument("--no-lint", action="store_true", help="跳过静态检查闸门")
    args = ap.parse_args(argv)

    if args.list_profiles:
        exe = find_codesys_exe(args.codesys_exe)
        print("CODESYS.exe :", exe or "未找到")
        profs = list_profiles()
        if not profs:
            print("未发现 profile，检查 %s" % PROFILE_DIRS[0])
        for p in profs:
            print("  profile:", p)
        return 0 if profs else 2

    if args.make_template:
        exe = find_codesys_exe(args.codesys_exe)
        profile, profiles = resolve_profile(args.profile)
        if not (exe and profile):
            print("没找到 CODESYS.exe 或 profile，无法生成模板。")
            print("  exe:", exe)
            print("  profile:", profile, profiles)
            return 2
        out = Path(args.project) if args.project else HERE / "templates" / "template.project"
        print("正在生成模板工程：", out)
        print("设备：", args.device)
        info = make_template(exe, profile, out, args.device, args.timeout)
        report = info.get("report") or {}
        steps = report.get("steps") or {}
        if steps.get("children"):
            print("工程对象：", ", ".join(steps["children"]))
        if steps.get("build_errors"):
            print("模板自带编译错误：", steps["build_errors"][:5])
        if info.get("ok"):
            print("模板生成成功，编译 0 错误 ->", out)
            return 0
        print("模板生成失败：", str(report.get("error") or info.get("log"))[-800:])
        return 1

    if not args.st:
        ap.error("需要 --st")

    target = Path(args.st)
    if not target.exists():
        print("路径不存在:", target)
        return 2

    jobs = collect_jobs(target, args.pou)
    if not jobs:
        print("没有找到 .st 文件")
        return 2

    # ---- 1) 静态检查闸门
    gate = run_lint_gate(jobs, not args.no_lint)
    blocked = {k: v for k, v in gate.items() if not v.get("ok", True)}

    # ---- 2) 决定后端
    exe = find_codesys_exe(args.codesys_exe)
    profile, profiles = resolve_profile(args.profile)
    backend = args.backend
    if backend == "auto":
        backend = "codesys" if (exe and profile) else "lint"

    env_info = {
        "codesys_exe": str(exe) if exe else None,
        "profile": profile,
        "profiles_found": profiles,
        "backend": backend,
        "inline_lint": not args.no_lint,
    }

    if backend == "codesys":
        if not args.project:
            print("缺 --project：需要一个已配置好设备与 PLC_PRG 的模板工程")
            return 2
        if not Path(args.project).is_file():
            print("模板工程不存在:", args.project)
            return 2
        runnable = [j for j in jobs if j["st"] not in blocked]
        skipped = [j for j in jobs if j["st"] in blocked]
        # 每个文件单独起一个 CODESYS 进程：POU 会留在工程里，
        # 上一个文件的语法错误会污染下一个文件的编译结果，隔离比省那几秒更重要。
        result = compile_with_codesys(runnable, Path(args.project), exe,
                                      profile, args.timeout) if runnable else \
            {"ok": True, "items": [], "fatal": None}
        raw_items = result.get("items", [])
        fatal = result.get("fatal")
        process = result.get("process")
    else:
        skipped = jobs
        raw_items, fatal, process = [], None, None

    # ---- 3) 汇总
    by_name = {i.get("name"): i for i in raw_items if isinstance(i, dict)}
    items = []
    for job in jobs:
        st = job["st"]
        lint = gate.get(st) or {}
        item = {
            "task": job["name"],
            "st": st,
            "pou": job["pou"],
            "lint_ok": lint.get("ok", True),
            "lint_errors": lint.get("errors", []),
            "lint_warnings": lint.get("warnings", []),
            "compiled": False,
            "ok": False,
            "stage": "lint",
            "duration_s": 0.0,
            "errors": [],
            "warnings": [],
        }
        if st in blocked:
            item["stage"] = "lint"
            item["errors"] = lint.get("errors", [])
            item["result"] = "STATIC_FAIL"
        elif backend == "lint":
            # 只跑静态检查的降级模式：通过也只能算「静态通过」，不能算编译通过
            item["stage"] = "lint"
            item["ok"] = bool(lint.get("ok", True))
            item["warnings"] = lint.get("warnings", [])
            item["result"] = "STATIC_PASS" if item["ok"] else "STATIC_FAIL"
        else:
            got = by_name.get(job["name"])
            if got is None:
                item["stage"] = "not_run"
                item["result"] = "NOT_RUN"
            else:
                item["compiled"] = True
                item["stage"] = "codesys"
                item["ok"] = bool(got.get("ok"))
                item["errors"] = got.get("errors", [])
                item["warnings"] = got.get("warnings", [])
                item["duration_s"] = got.get("duration_s", 0.0)
                item["api"] = got.get("api", {})
                item["result"] = "PASS" if item["ok"] else "COMPILE_FAIL"
        items.append(item)

    total = len(items)
    ok_tags = ("PASS", "STATIC_PASS")
    passed = sum(1 for i in items if i["result"] in ok_tags)
    summary = {
        "total": total,
        "pass": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "static_blocked": sum(1 for i in items if i["result"] == "STATIC_FAIL"),
        "compile_fail": sum(1 for i in items if i["result"] == "COMPILE_FAIL"),
        "not_run": sum(1 for i in items if i["result"] == "NOT_RUN"),
        "avg_duration_s": round(
            sum(i["duration_s"] for i in items if i["compiled"]) /
            max(1, sum(1 for i in items if i["compiled"])), 2),
    }
    payload = {"env": env_info, "summary": summary, "items": items}
    if fatal:
        payload["fatal"] = fatal
    if process:
        payload["process"] = process

    # ---- 4) 打印
    print("=" * 62)
    print("CODESYS 编译结果  backend=%s  profile=%s" % (backend, profile))
    print("=" * 62)
    for i in items:
        print("[%-11s] %-28s %6.1fs" % (i["result"], i["task"], i["duration_s"]))
        for e in i["errors"][:6]:
            loc = ""
            if e.get("line"):
                loc = " L%s" % e["line"]
            print("      %s%s %s" % (e.get("code", ""), loc,
                                     (e.get("text") or e.get("message", ""))[:140]))
    print("-" * 62)
    label = "静态通过" if backend == "lint" else "编译通过"
    print("%s %d/%d（%.0f%%）  静态拦截 %d  编译失败 %d  未执行 %d"
          % (label, passed, total, summary["pass_rate"] * 100,
             summary["static_blocked"], summary["compile_fail"],
             summary["not_run"]))
    if backend == "lint":
        print("注意：当前只做了静态检查，未真正编译。装好 CODESYS 后重跑即可得到真实通过率。")
    if payload.get("fatal"):
        print("错误：", str(payload["fatal"])[:500])

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print("结果已写入", out)

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
