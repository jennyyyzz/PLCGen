# -*- coding: utf-8 -*-
"""一键自检：把整条链路跑一遍，结果落到 out/run_<时间戳>/ 下。

用途有两个：
  1. 交付前确认工具链没被改坏；
  2. 你手动操作时，跑同一条命令就能得到结构完全相同的目录，方便逐项对比。

    python selftest.py
    python selftest.py --codesys-project templates/template.project

产物：
  out/run_YYYYmmdd_HHMM/
    env.json            环境探测（python / pyads / CODESYS / profile）
    01_lint.json        静态检查
    02_compile.json     编译（无 CODESYS 时降级为静态检查）
    03_tests_dry.json   用例结构校验
    04_tests_sim.json   本地仿真执行（正确实现）
    05_tests_bug.json   本地仿真执行（故意有 bug 的实现，应只过 2/3）
    06_report.md        可贴报告的用例表格
    summary.json        汇总（给实验表格用）
    run_log.txt         完整控制台输出
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
DEMO = HERE / "demo"
ST_OK = DEMO / "motor_start_stop.st"
ST_BUG = DEMO / "motor_start_stop.logicbug.st"
ST_BAD = DEMO / "motor_start_stop.bad.st"
CASE = DEMO / "motor_start_stop.testcase.json"


def tee(log: list, text: str):
    print(text)
    log.append(text)


def sh(cmd: list[str], log: list, timeout=600) -> tuple[int, float]:
    tee(log, "\n$ " + " ".join(str(c) for c in cmd))
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        for line in out.rstrip().split("\n"):
            tee(log, "  " + line)
        return p.returncode, round(time.time() - t0, 2)
    except subprocess.TimeoutExpired:
        tee(log, "  ! 超时 %ss" % timeout)
        return -1, round(time.time() - t0, 2)


def probe_env() -> dict:
    env = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
    }
    try:
        import pyads  # noqa
        env["pyads"] = getattr(pyads, "__version__", "unknown")
        env["pyads_importable"] = True
        env["pyads_note"] = "OK"
    except Exception as exc:
        env["pyads_importable"] = False
        env["pyads_note"] = str(exc).split("\n")[0][:200]

    sys.path.insert(0, str(HERE))
    try:
        from codesys_compile import find_codesys_exe, list_profiles
        exe = find_codesys_exe(None)
        env["codesys_exe"] = str(exe) if exe else None
        env["codesys_profiles"] = list_profiles()
    except Exception as exc:
        env["codesys_exe"] = None
        env["codesys_profiles"] = []
        env["codesys_probe_error"] = str(exc)
    return env


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="工具链一键自检")
    ap.add_argument("--codesys-project", help="模板工程；不传则只跑静态检查")
    ap.add_argument("--out-root", default=str(HERE / "out"))
    ap.add_argument("--tag", help="运行目录后缀，便于区分多次运行")
    args = ap.parse_args(argv)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.tag:
        stamp += "_" + args.tag
    run_dir = Path(args.out_root) / ("run_" + stamp)
    run_dir.mkdir(parents=True, exist_ok=True)

    log: list[str] = []
    summary = {"run_dir": str(run_dir), "started": stamp, "steps": []}

    env = probe_env()
    (run_dir / "env.json").write_text(
        json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")

    tee(log, "=" * 66)
    tee(log, "CODESYS 工具链自检  %s" % env["time"])
    tee(log, "=" * 66)
    tee(log, "python   : %s (%s)" % (env["python"], env["platform"]))
    tee(log, "pyads    : %s" % (env.get("pyads") or "不可用"))
    if not env.get("pyads_importable"):
        tee(log, "           -> %s" % env.get("pyads_note"))
    tee(log, "CODESYS  : %s" % (env.get("codesys_exe") or "未安装"))
    tee(log, "profiles : %s" % (env.get("codesys_profiles") or "无"))

    def record(name, rc, dur, path, note=""):
        summary["steps"].append({
            "step": name, "returncode": rc, "duration_s": dur,
            "output": str(path) if path else None, "note": note,
            "ok": rc == 0,
        })

    # 1 静态检查（含一个故意写坏的文件，应当被拦下）
    out1 = run_dir / "01_lint.json"
    rc1, d1 = sh([PY, str(HERE / "st_lint.py"), str(DEMO), "--json", str(out1),
                  "--quiet"], log)
    record("01 静态检查（demo 目录）", rc1, d1, out1,
           "含 1 个故意写坏的文件，预期 rc=1")

    # 2 编译
    out2 = run_dir / "02_compile.json"
    cmd2 = [PY, str(HERE / "codesys_compile.py"), "--st", str(DEMO),
            "--out", str(out2)]
    if args.codesys_project:
        cmd2 += ["--project", args.codesys_project, "--backend", "auto"]
    else:
        cmd2 += ["--backend", "lint"]
    rc2, d2 = sh(cmd2, log)
    record("02 编译", rc2, d2, out2,
           "有 CODESYS 时是真实编译，否则为静态降级")

    # 3 用例结构校验
    out3 = run_dir / "03_tests_dry.json"
    rc3, d3 = sh([PY, str(HERE / "run_tests.py"), "--case", str(CASE),
                  "--st", str(ST_OK), "--backend", "dry", "--out", str(out3)], log)
    record("03 用例结构校验", rc3, d3, out3)

    # 4 仿真执行（正确实现）
    out4 = run_dir / "04_tests_sim.json"
    out6 = run_dir / "06_report.md"
    rc4, d4 = sh([PY, str(HERE / "run_tests.py"), "--case", str(CASE),
                  "--st", str(ST_OK), "--backend", "sim", "--out", str(out4),
                  "--markdown", str(out6)], log)
    record("04 仿真执行（正确实现）", rc4, d4, out4, "预期 3/3 通过")

    # 4b Standard Library 字符串函数回归
    out4b = run_dir / "04b_tests_stdlib.json"
    rc4b, d4b = sh([PY, str(HERE / "run_tests.py"),
                    "--case", str(DEMO / "stdlib_strings.testcase.json"),
                    "--st", str(DEMO / "stdlib_strings.st"),
                    "--backend", "sim", "--out", str(out4b)], log)
    record("04b Standard 字符串函数", rc4b, d4b, out4b, "预期 1/1 通过")

    # 5 仿真执行（有 bug 的实现）
    out5 = run_dir / "05_tests_bug.json"
    rc5, d5 = sh([PY, str(HERE / "run_tests.py"), "--case", str(CASE),
                  "--st", str(ST_BUG), "--backend", "sim", "--out", str(out5)], log)
    record("05 仿真执行（缺陷实现）", rc5, d5, out5, "预期 2/3，TC03 失败")

    # 6 汇总
    def load(p):
        try:
            return json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            return {}

    c1 = load(out1)
    c2 = load(out2)
    t3 = load(out3)
    t4 = load(out4)
    t4b = load(out4b)
    t5 = load(out5)

    summary["results"] = {
        "lint": {"passed": c1.get("passed"), "total": c1.get("total")},
        "compile": c2.get("summary"),
        "tests_dry": {"pass": t3.get("pass"), "total": t3.get("total")},
        "tests_sim": {"pass": t4.get("pass"), "total": t4.get("total")},
        "tests_stdlib": {"pass": t4b.get("pass"), "total": t4b.get("total")},
        "tests_bug": {"pass": t5.get("pass"), "total": t5.get("total")},
    }
    summary["finished"] = datetime.now().isoformat(timespec="seconds")
    # demo 目录里除 .bad.st 之外都应通过
    exp_total = len(list(DEMO.glob("*.st")))
    exp_pass = exp_total - 1
    summary["expected"] = {"lint_total": exp_total, "lint_passed": exp_pass,
                           "tests_sim": "all", "tests_bug": 2}
    summary["all_expected"] = (
        c1.get("total") == exp_total and c1.get("passed") == exp_pass
        and t3.get("pass") == t3.get("total")
        and t4.get("pass") == t4.get("total")
        and t4b.get("pass") == t4b.get("total")
        and t5.get("pass") == 2
    )

    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    tee(log, "")
    tee(log, "-" * 66)
    tee(log, "汇总")
    tee(log, "  静态检查   : %s/%s 通过（预期 %s/%s，坏文件被拦下）"
        % (c1.get("passed"), c1.get("total"), exp_pass, exp_total))
    tee(log, "  编译       : %s" % json.dumps(
        c2.get("summary", {}), ensure_ascii=False))
    tee(log, "  用例结构   : %s/%s 合法" % (t3.get("pass"), t3.get("total")))
    tee(log, "  仿真(正确) : %s/%s 通过" % (t4.get("pass"), t4.get("total")))
    tee(log, "  Standard   : %s/%s 通过" % (t4b.get("pass"), t4b.get("total")))
    tee(log, "  仿真(缺陷) : %s/%s 通过" % (t5.get("pass"), t5.get("total")))
    tee(log, "  符合预期   : %s" % ("是" if summary["all_expected"] else "否"))
    tee(log, "  产物目录   : %s" % run_dir)

    (run_dir / "run_log.txt").write_text("\n".join(log), encoding="utf-8")
    print("\n日志: %s" % (run_dir / "run_log.txt"))
    return 0 if summary["all_expected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
