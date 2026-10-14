"""语义缓存标定：先测命中率，再定阈值。

## 为什么必须先测

缓存的收益 = 命中率 × 省下的那 19.6 秒。命中率低，这个优化就是白做。
而命中率只取决于「问题有多重合」——**这件事只能测，不能猜**。

## 用法（项目根目录，venv 已激活）

    python scripts/cache_hitrate.py                  # 用内置的 scripts/hr_questions.txt
    python scripts/cache_hitrate.py my_qs.txt        # 用自己的问题集（每行一个，# 是注释）
    python scripts/cache_hitrate.py my_qs.txt -r 3   # 整个问题表重复 3 遍，模拟稳态流量

## 输出四块

    ① 阈值扫描 —— 不同阈值下的命中率，用来选阈值
    ② 命中明细 —— 所有被判「命中」的问题对 + 相似度，**人工确认没有误命中**
    ③ 近邻分布 —— 每道题最像的另一道题，看整体重合度长什么样
    ④ 结论怎么读

⚠️ 本脚本不碰线上的 data/semantic_cache.json——落盘路径被指到临时文件，跑完删掉。
   它算相似度用的是**和 src/semantic_cache.py 完全相同的数学**：
   归一化向量直接点积（余弦相似度），没有 distance 换算那一层。
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ⚠️ 必须赶在 import config 之前设好：config 在 import 时就把环境变量读成常量了
_TMP_CACHE = Path(tempfile.gettempdir()) / "aboutme_semantic_cache_calib.json"
os.environ["SEMANTIC_CACHE_PATH"] = str(_TMP_CACHE)

# Windows 上 stdout 可能是 GBK，中文会直接 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np                      # noqa: E402
from src.embedder import embed_query    # noqa: E402


def load_questions(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def main() -> None:
    ap = argparse.ArgumentParser(description="语义缓存命中率标定")
    ap.add_argument("questions", nargs="?",
                    default=str(Path(__file__).parent / "hr_questions.txt"),
                    help="问题集文件，每行一个")
    ap.add_argument("-r", "--repeat", type=int, default=1,
                    help="问题表重复几遍（模拟稳态流量，第一遍全是 miss）")
    ap.add_argument("-t", "--thresholds", default="0.85,0.88,0.90,0.92,0.94,0.95,0.96,0.98",
                    help="要扫描的阈值，逗号分隔")
    args = ap.parse_args()

    questions = load_questions(Path(args.questions))
    if not questions:
        print(f"问题集是空的：{args.questions}")
        return
    if args.repeat > 1:
        questions = questions * args.repeat

    n = len(questions)
    print(f"问题集：{args.questions}")
    print(f"条目数：{n}（去重后 {len(set(questions))} 个不同问题）")

    print("\n正在向量化（首次会加载 bge-small 模型，约 5-10 秒）……")
    vecs = np.vstack([embed_query(q) for q in questions])   # (n, d)，已归一化
    sim = vecs @ vecs.T                                     # 两两余弦相似度

    thresholds = [float(x) for x in args.thresholds.split(",")]

    # ---------------- ① 阈值扫描 ----------------
    # 逐条累积模拟：第 i 条只能命中「前 i-1 条」里已经缓存过的
    print("\n" + "=" * 66)
    print("① 阈值扫描（逐条累积：第 i 条只能命中在它之前出现过的问题）")
    print("=" * 66)
    print(f"{'阈值':>7}{'命中数':>8}{'命中率':>9}")
    for t in thresholds:
        hits = sum(1 for i in range(1, n) if sim[i, :i].max() >= t)
        print(f"{t:>7.2f}{hits:>8}{hits / n * 100:>8.1f}%")

    # ---------------- ② 命中明细 ----------------
    probe = 0.95 if 0.95 in thresholds else thresholds[len(thresholds) // 2]
    print("\n" + "=" * 66)
    print(f"② 命中明细（阈值 {probe}）—— 逐条人工确认没有「看着像、意思不同」")
    print("=" * 66)
    pairs = [
        (float(sim[i, j]), questions[j], questions[i])
        for i in range(n) for j in range(i) if sim[i, j] >= probe
    ]
    pairs.sort(reverse=True)
    if not pairs:
        print("（没有任何一条命中——阈值定得太高，或问题集本来就分散）")
    for s, cached_q, cur_q in pairs:
        print(f"  {s:.4f}  「{cached_q}」→「{cur_q}」")

    # ---------------- ③ 近邻分布 ----------------
    print("\n" + "=" * 66)
    print("③ 每道题最像的另一道题（整体重合度长什么样）")
    print("=" * 66)
    np.fill_diagonal(sim, -1.0)              # 把自己排除掉
    best_idx = sim.argmax(axis=1)
    best_val = sim.max(axis=1)
    for i in np.argsort(-best_val):
        print(f"  {best_val[i]:.4f}  「{questions[i]}」↔「{questions[best_idx[i]]}」")

    # ---------------- ④ 怎么读 ----------------
    print("\n" + "=" * 66)
    print("④ 结论怎么读")
    print("=" * 66)
    print("  · 命中率高，但②里出现「意思明显不同」的对 → 阈值调高")
    print("  · 命中率低 → 真实流量问题分散，缓存收益有限（如实写，别硬吹）")
    print("  · 选定阈值后写进 .env：SEMANTIC_CACHE_THRESHOLD=0.9X")
    print("\n  ⚠️ 这只是「模拟流量」的命中率。真实命中率要看上线后 chat.stages 日志里的 cache_hit。")


if __name__ == "__main__":
    try:
        main()
    finally:
        _TMP_CACHE.unlink(missing_ok=True)
