# -*- coding: utf-8 -*-
"""判分器自测：证明它不会"什么都放过"，也不会因为精度差异误杀。

用法：
    .venv\Scripts\python.exe scripts\selftest_judge.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from judge import try_match, truth_from_text  # noqa: E402

CASES = []


def case(name, cand_rows, truth_rows, expect):
    CASES.append((name, cand_rows, truth_rows, expect))


# 1. 完全一致
case("完全一致", [["2017-01", 127545.67]], [["2017-01", 127545.67]], True)
# 2. 只是四舍五入位数不同（4.0868 vs 4.087）
case("精度不同", [[4.0868]], [[4.087]], True)
# 3. 数值真的错了
case("数值错误", [["2017-01", 127000.0]], [["2017-01", 127545.67]], False)
# 4. 多返回一列（模型顺手多算了订单数）
case("多一列", [["2017-01", 127545.67, 750]], [["2017-01", 127545.67]], True)
# 5. 列顺序反过来
case("列序相反", [[127545.67, "2017-01"]], [["2017-01", 127545.67]], True)
# 6. 少一行
case("少一行", [["2017-01", 127545.67]], [["2017-01", 127545.67], ["2017-02", 271298.65]], False)
# 7. 多一行
case("多一行", [["2017-01", 127545.67], ["2017-02", 271298.65]], [["2017-01", 127545.67]], False)
# 8. 行序不同（排序方向不一样）
case(
    "行序不同",
    [["2017-02", 2.0], ["2017-01", 1.0]],
    [["2017-01", 1.0], ["2017-02", 2.0]],
    True,
)


def main():
    failed = 0
    for name, cand, truth, expect in CASES:
        got, _ = try_match(cand, truth)
        ok = (got == expect)
        failed += 0 if ok else 1
        print(f"[{'OK ' if ok else 'BAD'}] {name}: 期望 {expect}, 实际 {got}")

    # 结论兜底：表是一张全州排名表，但结论明确答 0
    trace = {"conclusion": "数据中没有阿拉斯加州的订单，订单数为 0。"}
    got = truth_from_text(trace, {"rows": [[0]]})
    ok = got is True
    failed += 0 if ok else 1
    print(f"[{'OK ' if ok else 'BAD'}] 结论兜底: 期望 True, 实际 {got}")

    print(f"\n{'全部通过' if failed == 0 else f'{failed} 个用例不符合预期'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
