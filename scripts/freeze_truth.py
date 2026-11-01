# -*- coding: utf-8 -*-
"""
把题库里的标准答案 SQL 真跑一遍，把结果冻存成 truth.json。

为什么要"冻存"而不是手填：
  手填的标准答案会跟数据库对不上，而且改一次数据就要重填一次。
  这里每一题的结果都是数据库实际算出来的，谁都能复现。

有一类题会有两个标准答案（alt_reference_sql）：
  比如"配送最严重"既可以看平均延迟天数，也可以看延迟订单占比。
  两个都对，所以两个都存下来，判分时命中任一个即通过。

用法：
  python scripts/freeze_truth.py
"""
import json
import os
import sqlite3
from pathlib import Path

# 数据库位置：默认用桌面上 reviewmind 项目里的库，也可以用环境变量覆盖
DEFAULT_DB = Path.home() / "Desktop" / "reviewmind" / "olist.db"
DB_PATH = Path(os.environ.get("REVIEWMIND_DB", DEFAULT_DB))

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ROOT / "eval" / "questions.json"
TRUTH = ROOT / "eval" / "truth.json"


def run_sql(conn, sql):
    """执行一条查询，返回 (列名, 行列表)。"""
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return cols, rows


def normalize(rows):
    """把结果统一成可比较的形式：每个值转成字符串，行排序。

    为什么要排序：SQL 没写 ORDER BY 时行序不保证，
    但"结果集是否一致"只看内容不看顺序。
    """
    norm = []
    for row in rows:
        cells = []
        for v in row:
            if isinstance(v, float):
                cells.append(f"{v:.6f}")
            elif v is None:
                cells.append("NULL")
            else:
                cells.append(str(v))
        norm.append("|".join(cells))
    return sorted(norm)


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"找不到数据库：{DB_PATH}")

    spec = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    conn = sqlite3.connect(DB_PATH)

    truth = {}
    auto_count = 0
    for q in spec["questions"]:
        qid = q["id"]
        sql = q.get("reference_sql")
        if not sql:
            truth[qid] = {"judge": q["judge"], "note": "该题无标准 SQL，由人工按 judge_note 判定"}
            print(f"{qid}: 人工判定（无标准 SQL）")
            continue

        cols, rows = run_sql(conn, sql)
        entry = {
            "judge": q["judge"],
            "columns": cols,
            "row_count": len(rows),
            "rows": [list(r) for r in rows],
            "canonical": normalize(rows),
        }

        alt = q.get("alt_reference_sql")
        if alt:
            alt_cols, alt_rows = run_sql(conn, alt)
            entry["alt_columns"] = alt_cols
            entry["alt_row_count"] = len(alt_rows)
            entry["alt_canonical"] = normalize(alt_rows)

        truth[qid] = entry
        auto_count += 1
        print(f"{qid}: {len(rows)} 行 | 首行 {rows[0] if rows else None}"
              + ("  (+1 个备选口径)" if alt else ""))

    conn.close()
    TRUTH.write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n共 {len(spec['questions'])} 题，其中 {auto_count} 题已跑出真值 -> {TRUTH}")


if __name__ == "__main__":
    main()
