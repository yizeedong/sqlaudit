# -*- coding: utf-8 -*-
r"""把被测系统（ReviewMind）跑一遍题库，把每道题的完整轨迹落盘。

用法：
    .venv\Scripts\python.exe scripts\run_eval.py --system reviewmind-v1

产物：results\{system}.json
    每道题一条轨迹 = 问题 + 实际执行的 SQL + 查回的结果表 + 最终结论 + 耗时 + token
    这就是后面判分和归因的全部原材料。
"""
import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 被测系统所在目录：默认是仓库旁边的 reviewmind，可用环境变量覆盖
DEFAULT_REVIEWMIND = ROOT.parent / "reviewmind"
REVIEWMIND = Path(os.environ.get("REVIEWMIND_DIR", DEFAULT_REVIEWMIND))

# 让脚本能 import 被测系统
sys.path.insert(0, str(REVIEWMIND))


def load_questions():
    data = json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))
    return data["meta"], data["questions"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", default="reviewmind-v1", help="被测系统名字，用作结果文件名")
    ap.add_argument("--sleep", type=float, default=1.0, help="每题之间暂停秒数")
    ap.add_argument("--only", default="", help="只跑指定题号，逗号分隔，如 A1,C3")
    ap.add_argument("--repeat", type=int, default=1,
                    help="同一题重复跑几次，用来测稳定性（结论会不会漂移）")
    ap.add_argument("--agent", default="agent_core",
                    help="被测系统模块名：agent_core=ReviewMind v1，agent_v2=ReviewMind v2")
    args = ap.parse_args()

    import importlib
    agent_mod = importlib.import_module(args.agent)  # noqa: E402  延迟导入，避免没有依赖时直接崩

    meta, questions = load_questions()
    if args.only:
        wanted = {x.strip().upper() for x in args.only.split(",") if x.strip()}
        questions = [q for q in questions if q["id"].upper() in wanted]

    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{args.system}.json"

    traces = []
    started = datetime.now()
    total = len(questions) * max(1, args.repeat)
    print(
        f"[start] system={args.system} n={len(questions)} repeat={args.repeat} "
        f"calls={total} at {started:%Y-%m-%d %H:%M:%S}",
        flush=True,
    )

    done = 0
    for rnd in range(1, max(1, args.repeat) + 1):
        for q in questions:
            done += 1
            t0 = time.time()
            try:
                trace = agent_mod.ask_agent(q["question"])
            except Exception:
                trace = {
                    "question": q["question"],
                    "error": "harness_exception",
                    "stack": traceback.format_exc(),
                    "sql": None,
                    "tool_calls": [],
                    "result_columns": [],
                    "result_rows": [],
                    "conclusion": "",
                    "latency_ms": int((time.time() - t0) * 1000),
                    "usage": {},
                }
            trace.pop("df", None)
            trace["id"] = q["id"]
            trace["category"] = q["category"]
            trace["judge"] = q["judge"]
            trace["run"] = rnd
            traces.append(trace)
            print(
                f"[{done:03d}/{total}] run{rnd} {q['id']:<3} "
                f"err={trace.get('error')} rows={len(trace.get('result_rows') or [])} "
                f"{trace.get('latency_ms')}ms",
                flush=True,
            )
            time.sleep(args.sleep)

    payload = {
        "system": args.system,
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "repeat": max(1, args.repeat),
        "eval_meta": meta,
        "traces": traces,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[done] -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
