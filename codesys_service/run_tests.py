# -*- coding: utf-8 -*-
"""测试用例执行器

用例格式对齐课程给的《测试用例模板与示例》：
每个用例包含 编号/名称、所属题目、初始状态、输入与步骤、预期输出、覆盖内容、实际输出。

两种后端
  dry  只做结构校验 + 与 ST 声明交叉检查，不连 PLC。用例写完就能先验一遍格式，
       避免跑到 PLC 上才发现变量名拼错。
  sim  用 st_sim.py 在本地按扫描周期执行 ST（离线仿真），得到真实的功能性结果，
       不需要 CODESYS。只支持 IF/赋值/逻辑运算子集，遇到不支持的语句会明确报错。
  ads  通过 pyads 连 CODESYS Control Win，逐周期写输入、读输出、比对预期。
       （需要先装 pyads、TcAdsDll，并下载带符号配置的工程）

用法
  python run_tests.py --case demo/motor_start_stop.testcase.json --st demo/motor_start_stop.st
  python run_tests.py --case cases/ --st out/st/ --backend ads --ams 127.0.0.1.1.1
  python run_tests.py --case demo/ --markdown out/test_report.md

退出码：0 = 全部 PASS（dry 模式 = 全部结构合法）；1 = 有失败；2 = 参数/环境问题
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

TYPE_MAP = {
    "BOOL": "PLCTYPE_BOOL",
    "BYTE": "PLCTYPE_BYTE",
    "WORD": "PLCTYPE_WORD",
    "DWORD": "PLCTYPE_DWORD",
    "SINT": "PLCTYPE_SINT",
    "INT": "PLCTYPE_INT",
    "DINT": "PLCTYPE_DINT",
    "USINT": "PLCTYPE_USINT",
    "UINT": "PLCTYPE_UINT",
    "UDINT": "PLCTYPE_UDINT",
    "REAL": "PLCTYPE_REAL",
    "LREAL": "PLCTYPE_LREAL",
}

# 数组元素下标写法：Name[0] / Name[1] 等（问题 4-3）
ARRAY_SUB_RE = re.compile(r"\[\s*-?\w+\s*\]")


def _base_name(name: str) -> str:
    """把 `Slab_Fault_History[0]` 归一成 `SLAB_FAULT_HISTORY`（数组基名）。"""
    return ARRAY_SUB_RE.sub("", str(name).strip()).strip().upper()


# ------------------------------------------------------------------ 用例读写

def load_case(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    data.setdefault("cases", [])
    data.setdefault("scan_ms", 20)
    data["_file"] = str(path)
    return data


def collect_cases(target: Path) -> list[dict]:
    files = sorted(target.rglob("*.testcase.json")) if target.is_dir() else [target]
    return [load_case(f) for f in files]


def st_declarations(st_path: Path | None) -> dict:
    """从 ST 文件读出声明变量表 {NAME: type}。"""
    if not st_path or not Path(st_path).is_file():
        return {}
    try:
        from st_lint import strip_comments, collect_declarations, Report
    except Exception:
        return {}
    text = strip_comments(Path(st_path).read_text(encoding="utf-8", errors="replace"))
    declared, _types = collect_declarations(text, Report(str(st_path)))
    return {k: v[2] for k, v in declared.items()}


# ------------------------------------------------------------------ dry 后端

def run_dry(case: dict, declared: dict) -> dict:
    """不执行，只验证用例本身是否可用。返回结构 + 每个用例的 VALID/INVALID。"""
    issues = []
    iface = {v["name"].upper(): v for v in case.get("interface", [])}

    referenced = set()
    for c in case["cases"]:
        cid = c.get("id", "?")
        if not c.get("steps"):
            issues.append(f"{cid}: 没有任何步骤")
        for key in ("name", "coverage", "initial_state"):
            if not c.get(key):
                issues.append(f"{cid}: 缺少字段 {key}")
        for s in c.get("steps", []):
            for grp in ("inputs", "expect"):
                for var in (s.get(grp) or {}):
                    base = _base_name(var)
                    referenced.add(base)
                    if iface and base not in iface and \
                            declared and base not in declared:
                        issues.append(
                            f"{cid} 周期{s.get('cycle')}: {grp} 里的 {var} "
                            f"既不在 interface 也不在 ST 声明里")
            if not s.get("expect"):
                issues.append(f"{cid} 周期{s.get('cycle')}: 没有预期输出")

    # 接口声明与 ST 声明互相校对（数组元素 Name[0] 归一到基名再比对；
    # 元素类型（BOOL）与数组类型（ARRAY..OF BOOL）字符串不同，跳过类型比对）
    for name, spec in iface.items():
        base = _base_name(name)
        if declared and base not in declared:
            issues.append(f"interface 里的 {name} 在 ST 文件里没有声明")
        elif declared and base == name and declared.get(base):
            t_if = str(spec.get("type", "")).upper()
            t_st = declared[base].upper()
            if t_if and t_if != t_st:
                issues.append(f"{name} 类型不一致：interface={t_if} ST={t_st}")

    unused = [k for k in declared if k not in referenced] if declared else []

    return {
        "task_id": case.get("task_id"),
        "file": case.get("_file"),
        "mode": "dry",
        "valid": not issues,
        "issues": issues,
        "unreferenced_vars": unused,
        "cases": [{
            "id": c.get("id"), "name": c.get("name"),
            "coverage": c.get("coverage"),
            "initial_state": c.get("initial_state"),
            "result": "VALID" if not issues else "INVALID",
            "steps": [{"cycle": s.get("cycle"),
                       "inputs": s.get("inputs", {}),
                       "expect": s.get("expect", {}),
                       "actual": {},
                       "check": s.get("check", "")} for s in c.get("steps", [])],
        } for c in case["cases"]],
    }


# ------------------------------------------------------------------ sim 后端

def run_sim(case: dict, st_path: Path) -> dict:
    """用本地 ST 解释器执行，得到功能性结果（无需 CODESYS）。"""
    from st_sim import Program, Unsupported

    text = Path(st_path).read_text(encoding="utf-8", errors="replace")
    scan_ms = max(int(case.get("scan_ms", 20)), 1)
    try:
        prog = Program(text, scan_ms=scan_ms)
    except Unsupported as exc:
        # 解析期就失败（语法/字面量不支持等）：每个用例记 NOT_RUN 并带原因，
        # 而不是让整个后端静默消失（total=0 会让人误以为没跑到用例）
        return {
            "task_id": case.get("task_id"),
            "file": case.get("_file"),
            "mode": "sim",
            "st": str(st_path),
            "error": str(exc),
            "cases": [{
                "id": c.get("id"), "name": c.get("name"),
                "coverage": c.get("coverage"),
                "initial_state": c.get("initial_state"),
                "result": "NOT_RUN",
                "steps": [{"cycle": "-", "inputs": {}, "expect": {}, "actual": {},
                           "check": "", "ok": False,
                           "diff": ["解释器不支持: %s" % exc]}],
            } for c in case.get("cases", [])],
        }

    iface = {v["name"].upper(): v for v in case.get("interface", [])}
    outputs = [k for k, v in iface.items() if v.get("dir") == "output"]

    results = []
    for c in case["cases"]:
        prog.reset()
        steps = []
        case_ok = True
        try:
            for s in c.get("steps", []):
                for name, val in (s.get("inputs") or {}).items():
                    t = prog.var_type(name)
                    prog.write(name, bool(val) if t == "BOOL" else val)
                # hold_ms：本步输入保持的时长（默认一个扫描周期）。
                # 定时器类用例不用写几百个 step，一个 step + hold_ms 即可。
                n = max(1, int(round((s.get("hold_ms") or scan_ms) / scan_ms)))
                for _ in range(n):
                    prog.scan()
                want_names = list((s.get("expect") or {}).keys())
                names = want_names or outputs
                actual = {n: prog.read(n) for n in names}
                diffs = []
                for name, want in (s.get("expect") or {}).items():
                    got = actual.get(name)
                    if _norm(got) != _norm(want) and not _close(_norm(got), _norm(want)):
                        diffs.append("%s 预期 %s 实际 %s" % (name, want, got))
                ok = not diffs
                case_ok = case_ok and ok
                steps.append({
                    "cycle": s.get("cycle"),
                    "inputs": s.get("inputs", {}),
                    "expect": s.get("expect", {}),
                    "actual": actual,
                    "check": s.get("check", ""),
                    "ok": ok,
                    "diff": diffs,
                })
            result = "PASS" if case_ok else "FAIL"
        except Unsupported as exc:
            result = "NOT_RUN"
            steps.append({"cycle": "-", "inputs": {}, "expect": {}, "actual": {},
                          "check": "", "ok": False,
                          "diff": ["解释器不支持: %s" % exc]})
        results.append({
            "id": c.get("id"), "name": c.get("name"),
            "coverage": c.get("coverage"),
            "initial_state": c.get("initial_state"),
            "result": result,
            "steps": steps,
        })

    return {
        "task_id": case.get("task_id"),
        "file": case.get("_file"),
        "mode": "sim",
        "st": str(st_path),
        "cases": results,
    }


# ------------------------------------------------------------------ ads 后端

def _ctype(pyads, type_name: str):
    attr = TYPE_MAP.get(str(type_name).upper())
    if attr is None:
        raise ValueError("不支持的变量类型: %s" % type_name)
    return getattr(pyads, attr)


def run_ads(case: dict, ams: str, port: int, ip: str, settle_ms: int) -> dict:
    try:
        import pyads  # noqa
    except Exception as exc:
        raise SystemExit(
            "pyads 不可用：%s\n"
            "  - 未安装：pip install pyads\n"
            "  - 缺 TcAdsDll.dll：安装 TwinCAT ADS 或把 TcAdsDll.dll 放到 PATH / "
            "site-packages\\pyads 下" % exc)

    iface = {v["name"]: v for v in case.get("interface", [])}
    inputs = {k: v for k, v in iface.items() if v.get("dir") == "input"}
    outputs = {k: v for k, v in iface.items() if v.get("dir") == "output"}
    if not inputs or not outputs:
        raise SystemExit("interface 里必须同时有 input 和 output 定义")

    plc = pyads.Connection(ams, port, ip)
    plc.open()
    scan = max(int(case.get("scan_ms", 20)), 1)
    wait = max(scan * 2, settle_ms) / 1000.0

    def write_inputs(values: dict):
        for name, val in values.items():
            spec = iface.get(name)
            ctype = _ctype(pyads, (spec or {}).get("type", "BOOL"))
            plc.write_by_name(name, val, ctype)

    def reset():
        write_inputs({n: 0 for n in inputs})

    results = []
    try:
        for c in case["cases"]:
            steps = []
            case_ok = True
            reset()
            time.sleep(wait)
            for s in c.get("steps", []):
                write_inputs(s.get("inputs", {}))
                # hold_ms：本步输入保持的时长（默认一个周期等待）
                time.sleep(max(wait, (s.get("hold_ms") or 0) / 1000.0))
                actual = {}
                for name, spec in outputs.items():
                    ctype = _ctype(pyads, spec.get("type", "BOOL"))
                    actual[name] = plc.read_by_name(name, ctype)

                expect = s.get("expect", {})
                diffs = []
                for name, want in expect.items():
                    got = actual.get(name)
                    if _norm(got) != _norm(want):
                        diffs.append("%s 预期 %s 实际 %s" % (name, want, got))
                step_ok = not diffs
                case_ok = case_ok and step_ok
                steps.append({
                    "cycle": s.get("cycle"),
                    "inputs": s.get("inputs", {}),
                    "expect": expect,
                    "actual": actual,
                    "check": s.get("check", ""),
                    "ok": step_ok,
                    "diff": diffs,
                })
            results.append({
                "id": c.get("id"), "name": c.get("name"),
                "coverage": c.get("coverage"),
                "initial_state": c.get("initial_state"),
                "result": "PASS" if case_ok else "FAIL",
                "steps": steps,
            })
    finally:
        try:
            reset()
            plc.close()
        except Exception:
            pass

    return {
        "task_id": case.get("task_id"),
        "file": case.get("_file"),
        "mode": "ads",
        "ams": "%s:%s" % (ams, port),
        "cases": results,
    }


def _fmt(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v)


def _norm(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    try:
        return int(v)
    except Exception:
        return v


def _close(a, b):
    """数值近似相等（相对容差 1e-6）：浮点输出的期望值常写 33.333333 这类近似数。"""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
    return False


# ------------------------------------------------------------------ 报告渲染

def render_markdown(result: dict) -> str:
    """按课程模板的表格形式输出，可直接贴进实验报告。"""
    lines = []
    title = result.get("task_id") or "测试用例"
    lines.append("### %s（%s）" % (title, result.get("mode")))
    lines.append("")
    for c in result.get("cases", []):
        lines.append("**%s %s**" % (c.get("id"), c.get("name")))
        if c.get("coverage"):
            lines.append("覆盖内容：%s" % c["coverage"])
        if c.get("initial_state"):
            lines.append("初始状态：%s" % c["initial_state"])
        lines.append("")
        cols = []
        for s in c.get("steps", []):
            for k in list(s.get("inputs", {})) + list(s.get("expect", {})):
                if k not in cols:
                    cols.append(k)
        head = ["周期"] + cols + ["实际输出", "检查内容", "结果"]
        lines.append("| " + " | ".join(head) + " |")
        lines.append("|" + "|".join(["---"] * len(head)) + "|")
        for s in c.get("steps", []):
            row = [str(s.get("cycle"))]
            for k in cols:
                if k in s.get("inputs", {}):
                    row.append(_fmt(s["inputs"][k]))
                elif k in s.get("expect", {}):
                    row.append(_fmt(s["expect"][k]))
                else:
                    row.append("-")
            actual = s.get("actual") or {}
            row.append("; ".join("%s=%s" % (k, _fmt(v)) for k, v in actual.items()) or "-")
            row.append(s.get("check", ""))
            row.append(str(s.get("result") or ("PASS" if s.get("ok") else "-")))
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------ main

def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="测试用例执行器")
    ap.add_argument("--case", required=True, help="用例 JSON 文件或目录")
    ap.add_argument("--st", help="对应 ST 文件（用于变量交叉检查）")
    ap.add_argument("--backend", default="dry", choices=["dry", "sim", "ads"])
    ap.add_argument("--out", help="结果 JSON 输出路径")
    ap.add_argument("--markdown", help="按课程模板输出 Markdown 表格")
    ap.add_argument("--ams", default="127.0.0.1.1.1", help="ADS AMS NetId")
    ap.add_argument("--port", type=int, default=851, help="ADS 端口")
    ap.add_argument("--ip", default="127.0.0.1", help="PLC IP")
    ap.add_argument("--settle-ms", type=int, default=50, help="每周期等待毫秒数")
    args = ap.parse_args(argv)

    target = Path(args.case)
    if not target.exists():
        print("用例文件不存在:", target)
        return 2

    cases = collect_cases(target)
    if not cases:
        print("没有找到 *.testcase.json")
        return 2

    declared = st_declarations(Path(args.st) if args.st else None)
    results = []
    if args.backend in ("sim", "ads") and not args.st:
        print("--backend %s 需要 --st 指定要执行的 ST 文件" % args.backend)
        return 2

    for case in cases:
        if args.backend == "dry":
            results.append(run_dry(case, declared))
        elif args.backend == "sim":
            results.append(run_sim(case, Path(args.st)))
        else:
            results.append(run_ads(case, args.ams, args.port, args.ip,
                                   args.settle_ms))

    # ---- 汇总
    total = passed = 0
    for r in results:
        for c in r["cases"]:
            total += 1
            if c["result"] in ("PASS", "VALID"):
                passed += 1

    print("=" * 60)
    print("测试执行结果  backend=%s" % args.backend)
    print("=" * 60)
    for r in results:
        print("%s  (%s)" % (r.get("task_id"), Path(r.get("file", "")).name))
        if r.get("issues"):
            for i in r["issues"][:10]:
                print("   ! " + i)
        for c in r["cases"]:
            print("   [%-7s] %s %s" % (c["result"], c.get("id"), c.get("name")))
            for s in c.get("steps", []):
                if s.get("diff"):
                    for d in s["diff"]:
                        print("        周期%s %s" % (s.get("cycle"), d))
    print("-" * 60)
    if args.backend == "dry":
        print("结构校验：%d/%d 个用例合法（未执行，仅检查格式与变量一致性）"
              % (passed, total))
    else:
        print("测试通过：%d/%d（%.0f%%）"
              % (passed, total, (passed / total * 100) if total else 0))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"backend": args.backend, "total": total, "pass": passed,
                   "pass_rate": round(passed / total, 4) if total else 0,
                   "results": results}
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print("结果已写入", out)

    if args.markdown:
        md = "\n\n".join(render_markdown(r) for r in results)
        p = Path(args.markdown)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md, encoding="utf-8")
        print("报告表格已写入", p)

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
