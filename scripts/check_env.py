"""SQLAudit 环境自检：跑一遍就知道缺什么。

用法（在 sqlaudit 目录下）：
    .venv\\Scripts\\python.exe scripts\\check_env.py

全部打 ✅ 就说明可以跑评测了。
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

# 让中文在 Windows 控制台正常显示（不改成 UTF-8 会显示乱码）
if os.name == "nt":
    os.system("chcp 65001 > nul")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
REVIEWMIND = Path(os.environ.get("REVIEWMIND_DIR", ROOT.parent / "reviewmind"))

ok_count = 0
fail_count = 0


def ok(msg):
    global ok_count
    ok_count += 1
    print(f"  [OK]   {msg}")


def bad(msg, hint=""):
    global fail_count
    fail_count += 1
    print(f"  [FAIL] {msg}")
    if hint:
        print(f"         -> {hint}")


def section(title):
    print(f"\n{title}")


# ---------- 1. Python ----------
section("1. Python 环境")
v = sys.version_info
if v >= (3, 10):
    ok(f"Python {v.major}.{v.minor}.{v.micro}  ({sys.executable})")
else:
    bad(f"Python {v.major}.{v.minor} 太旧", "需要 3.10 及以上")

if sys.prefix != sys.base_prefix:
    ok(f"当前在虚拟环境里：{sys.prefix}")
else:
    bad("没有在虚拟环境里", r"先运行 .venv\Scripts\activate")

# ---------- 2. 依赖 ----------
section("2. 依赖包")
for pkg in ["openai", "httpx", "pandas", "dotenv"]:
    spec = importlib.util.find_spec(pkg)
    if spec is None:
        bad(f"缺 {pkg}", f'.venv\\Scripts\\python.exe -m pip install -r requirements.txt')
    else:
        try:
            from importlib.metadata import version
            name = {"dotenv": "python-dotenv"}.get(pkg, pkg)
            ok(f"{pkg} {version(name)}")
        except Exception:
            ok(f"{pkg} 已安装")

# ---------- 3. API Key ----------
section("3. API Key")
env_file = ROOT / ".env"
if env_file.exists():
    ok(f"找到 .env（{env_file}）")
else:
    fallback = REVIEWMIND / ".env"
    if fallback.exists():
        env_file = fallback
        ok(f"没找到 sqlaudit/.env，改用被测系统的 {fallback}")
    else:
        bad(".env 不存在", r"复制 .env.example 为 .env，再填 DEEPSEEK_API_KEY")

key = os.environ.get("DEEPSEEK_API_KEY", "")
if not key:
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        key = os.environ.get("DEEPSEEK_API_KEY", "")
    except Exception:
        pass
if key:
    ok(f"DEEPSEEK_API_KEY 已配置（{key[:6]}...{key[-4:]}，长度 {len(key)}）")
else:
    bad("DEEPSEEK_API_KEY 没读到", ".env 里写一行：DEEPSEEK_API_KEY=sk-xxxx")

# ---------- 4. 被测系统 ----------
section("4. 被测系统（ReviewMind）")
if REVIEWMIND.exists():
    ok(f"目录存在：{REVIEWMIND}")
    if (REVIEWMIND / "agent_core.py").exists():
        ok("agent_core.py 存在（v1）")
    else:
        bad("agent_core.py 不存在", "被测系统缺文件，评测跑不了")
    if (REVIEWMIND / "agent_v2.py").exists():
        ok("agent_v2.py 存在（v2）")
    else:
        print("  [SKIP] agent_v2.py 不存在（v2 对照跑不了，但 v1 还能跑）")
    db = REVIEWMIND / "olist.db"
    if db.exists():
        ok(f"olist.db 存在（{db.stat().st_size / 1024 / 1024:.0f} MB）")
    else:
        bad("olist.db 不存在", "数据库没建好，SQL 查不了")
else:
    bad(f"目录不存在：{REVIEWMIND}", "设置环境变量 REVIEWMIND_DIR 指向 reviewmind 目录")

# ---------- 5. 题库与真值 ----------
section("5. 题库与真值")
for name, path in [("questions.json", ROOT / "eval" / "questions.json"),
                   ("truth.json", ROOT / "eval" / "truth.json")]:
    if not path.exists():
        bad(f"{name} 不存在（{path}）")
        continue
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if name == "questions.json":
            n = len(data.get("questions", []))
            title = data.get("meta", {}).get("name", "")
            ok(f"{name} 可解析：{n} 题（{title}）")
        else:
            ok(f"{name} 可解析：{len(data)} 条真值")
    except Exception as exc:
        bad(f"{name} 解析失败：{exc}")

# ---------- 6. 结果目录 ----------
section("6. 输出目录")
res = ROOT / "results"
try:
    res.mkdir(exist_ok=True)
    probe = res / ".write_probe"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    ok(f"results/ 可写：{res}")
except Exception as exc:
    bad(f"results/ 不可写：{exc}")

# ---------- 汇总 ----------
print("\n" + "=" * 46)
if fail_count == 0:
    print(f"全部通过（{ok_count} 项）。下一步：")
    print(r"  .venv\Scripts\python.exe scripts\run_eval.py --system smoke --only A1")
else:
    print(f"通过 {ok_count} 项，失败 {fail_count} 项。先修失败项，再跑评测。")
print("=" * 46)
sys.exit(0 if fail_count == 0 else 1)
