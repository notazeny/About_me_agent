"""Rerank 精排：用交叉编码器对候选片段重打分。"""
from FlagEmbedding import FlagReranker
from . import config


_reranker = None


def get_reranker():
    """懒加载 rerank 模型（首次调用才下载/加载，之后复用）。"""
    global _reranker
    if _reranker is None:
        # use_fp16=False：CPU 环境用全精度，避免 fp16 不支持导致报错
        _reranker = FlagReranker(config.RERANK_MODEL, use_fp16=False)
    return _reranker


def rerank(query, candidates, top_k=config.TOP_K):
    """对候选片段用交叉编码器重打分，返回分数最高的 top_k 个。

    candidates: [{text, source, ...}]  ← 粗召融合后的候选
    返回: [{text, source, score}]，score 是 rerank 分数（logits，不是 0-1）
    """
    # 防御性：如果候选为空，直接返回空列表
    if not candidates:
        return []
    
    # 把 query 和每个候选的 text 拼成 pairs = [[query, c["text"]], ...]
    pairs = [[query, c["text"]] for c in candidates]

    # 调 get_reranker().compute_score(pairs) 拿到分数列表
    reranker = get_reranker()
    scores = reranker.compute_score(pairs)    # 返回 list[float]

    # 使用 zip 将候选和分数一一对应，再按分数降序排序
    scored = sorted(
        zip(candidates, scores),
        key=lambda x: x[1],  # x[1] 是分数
        reverse=True
    )
    # 取前 top_k 个，每个 dict 带上 "score" 字段返回
    results = []
    for c, s in scored[:top_k]:
        # 复制候选内容，避免修改原始数据；添加 score 字段
        item = {
            "text": c["text"],
            "source": c["source"],
            "score": s
        }
        results.append(item)

    return results
