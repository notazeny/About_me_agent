"""语义缓存：缓存「问题 → 检索片段」的映射，命中就跳过 rerank。

## 为什么缓存的是「检索结果」，不是「最终答案」

检索是个**纯函数**：`question -> chunks`，**与对话历史无关**——
history 只进 `build_prompt`，不进 `retrieve_with_rerank`。
所以同一句话，无论在第 1 轮还是第 5 轮问，检索结果永远一样，**缓存它永远安全**。

答案不一样，它受两个东西影响：
  1. `build_prompt(question, chunks, history=...)` 会带上最近几轮对话 →
     同一句话在不同轮次本就该有不同的回答；
  2. `TEMPERATURE=0.3` → 同一句话两次生成的措辞就不一样。

缓存答案 = 把「某一次转述」升格成「此后所有类似问题的官方答案」，
还会让 LLM 不再运行、把 `chat.stages` 的分段打点整条打断（**优化把可观测性干掉**）。
所以**只缓存检索结果**。完整取舍见 `learn+/性能优化待办.md`。

## 收益

rerank 占端到端 24 秒里的 19.6 秒。命中后检索从 ~21.7s 降到 ~0.05s，
用户感受到的首字延迟只剩 LLM 的那 1.15s ≈ **1.2s**。

## 相似度怎么算

缓存里存的是**已归一化**的问题向量。归一化向量下 `余弦相似度 == 点积`，
所以一次矩阵乘即可，**不需要任何 distance → similarity 的换算**。

（这也正是没用 ChromaDB 第二集合的原因：那边 query 返回的是 distance，
归一化向量下是 `cos = 1 - d/2`，多一层容易写错、且写错了不报错、只静默失准。）

## 阈值

`config.SEMANTIC_CACHE_THRESHOLD` 默认 0.95，可用环境变量 `SEMANTIC_CACHE_THRESHOLD` 覆盖。
**怎么定出来的**见 `scripts/cache_hitrate.py`——先测再定，别拍脑袋。
"""
from __future__ import annotations

import json
import logging
import threading

import numpy as np

from . import config
from .embedder import embed_query

logger = logging.getLogger(__name__)

# 当前线程最近一次 lookup 的摘要，供 chat 日志标注 cache_hit / 相似度。
# 用 threading.local 而不是全局变量：FastAPI 的同步路由跑在线程池里，
# 多个请求会同时走 lookup，共享一个全局变量会串号。
_local = threading.local()

# 缓存主体。三个 list 同增同减，读写都在 _lock 下，保证长度对齐。
_lock = threading.Lock()
_questions: list[str] = []          # 原始问题文本（调试 / 落盘用）
_vectors: list[np.ndarray] = []     # 已归一化的问题向量
_results: list[list[dict]] = []     # 对应的检索结果 [{text, source, score}]
_loaded = False

# 累计统计：离线标定脚本直接读它；以后也可以定期打进日志看线上命中率
stats = {"hit": 0, "miss": 0, "stored": 0, "loaded": 0}


def _set_last(**fields) -> None:
    _local.last = fields


def last_lookup() -> dict:
    """当前线程最近一次 lookup 的摘要。没调用过时返回一个安全的默认值。"""
    return getattr(_local, "last", {"hit": False, "score": 0.0, "reason": "未调用"})


def size() -> int:
    with _lock:
        return len(_results)


def _ensure_loaded() -> None:
    """惰性载入：第一次用到缓存时才读磁盘，避免 import 阶段就碰文件。"""
    global _loaded
    if _loaded:
        return

    with _lock:
        if _loaded:
            return
        _loaded = True

        path = config.SEMANTIC_CACHE_PATH
        if path is None or not path.exists():
            return

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("语义缓存文件读不出来，按空缓存继续：%s", exc)
            return

        for item in payload.get("entries", []):
            try:
                vec = np.asarray(item["vector"], dtype=np.float32)
            except Exception:
                continue
            norm = float(np.linalg.norm(vec))
            if norm == 0:
                continue
            _questions.append(item["question"])
            _vectors.append(vec / norm)   # 落盘再读回来可能有浮点漂移，重新归一
            _results.append(item["chunks"])

        stats["loaded"] = len(_results)
        logger.info("语义缓存载入 %d 条", len(_results))


def _matrix() -> np.ndarray | None:
    """把已缓存的向量堆成 (n, d) 矩阵；空缓存返回 None。

    缓存条目通常只有几十条，每次 vstack 的开销远小于一次 rerank（约 20 秒），
    所以不做增量维护——简单优先。
    """
    if not _vectors:
        return None
    return np.vstack(_vectors)


def lookup(question: str) -> tuple[list[dict] | None, float]:
    """查缓存。返回 (检索结果, 最高相似度)；未命中时第一个元素为 None。

    永远不把异常抛给调用方——缓存只是加速手段，出问题就当没命中。
    """
    if not config.SEMANTIC_CACHE_ENABLED:
        _set_last(hit=False, score=0.0, reason="缓存已关闭")
        return None, 0.0

    _ensure_loaded()
    if not _vectors:
        _set_last(hit=False, score=0.0, reason="缓存为空")
        return None, 0.0

    qvec = embed_query(question)          # 已归一化

    with _lock:
        matrix = _matrix()
        results = list(_results)          # 浅拷贝：连同矩阵拿到一致的长度快照

    sims = matrix @ qvec                  # 归一化向量：点积 == 余弦相似度
    idx = int(np.argmax(sims))
    best = float(sims[idx])

    if best >= config.SEMANTIC_CACHE_THRESHOLD:
        stats["hit"] += 1
        _set_last(hit=True, score=best, reason="命中", matched=_questions[idx])
        return results[idx], best

    stats["miss"] += 1
    _set_last(hit=False, score=best, reason="相似度不足")
    return None, best


def store(question: str, chunks: list[dict]) -> None:
    """把一次完整检索的结果写进缓存。"""
    if not config.SEMANTIC_CACHE_ENABLED or not chunks:
        return

    _ensure_loaded()

    # 向量化放在锁外面：模型推理约 0.05s，没必要占着锁
    qvec = np.asarray(embed_query(question), dtype=np.float32)

    with _lock:
        if question in _questions:        # 一模一样的问题不重复存
            return
        _questions.append(question)
        _vectors.append(qvec)
        _results.append(chunks)
        stats["stored"] += 1

    _save()


def reset() -> None:
    """清空内存缓存（供离线标定脚本和测试使用，不碰磁盘文件）。"""
    global _loaded
    with _lock:
        _questions.clear()
        _vectors.clear()
        _results.clear()
        _loaded = True                    # 标定脚本不希望它再去读线上缓存
    stats.update(hit=0, miss=0, stored=0, loaded=0)


def _save() -> None:
    path = config.SEMANTIC_CACHE_PATH
    if path is None:
        return

    with _lock:
        payload = {
            "version": 1,
            "threshold": config.SEMANTIC_CACHE_THRESHOLD,
            "entries": [
                {"question": q, "vector": v.tolist(), "chunks": c}
                for q, v, c in zip(_questions, _vectors, _results)
            ],
        }

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)                 # 原子替换：避免读到写了一半的文件
    except Exception as exc:
        logger.warning("语义缓存落盘失败（不影响本次回答）：%s", exc)
