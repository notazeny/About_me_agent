"""纯函数：加权 RRF 融合。

★ 单独成模块不是为了"分层好看"，是为了**可测性**。

   `weighted_rrf` 只是「两个有序列表 → 一个有序列表」的纯计算，
   不碰模型、不碰数据库。但它原来住在 `hybrid_retriever.py` 里，
   而同模块顶层 import 了 embedder / reranker / vector_store
   → 连锁拉进 torch / sentence-transformers / chromadb。

   结果：想测这一行公式，得先装 1.5GB 的依赖。
   抽出来之后，测试只 import 本模块（+ config），毫秒级、零重依赖。

   `hybrid_retriever` 仍然 re-export 这个名字，调用方不受影响。
"""
from . import config


def weighted_rrf(vector_ranked, bm25_ranked, k=config.RRF_K, weights=config.HYBRID_WEIGHTS):
    """加权 RRF 融合：两个 [(id, ...)] 列表（已按相关度降序）→ [(id, 融合分)] 降序。

    公式：每个列表里，排名 rank（从 0 起）的文档累加 weight / (k + rank + 1)。
    """
    scores = {}
    for lst, w in [(vector_ranked, weights[0]), (bm25_ranked, weights[1])]:
        for rank, (doc_id, _) in enumerate(lst):
            scores[doc_id] = scores.get(doc_id, 0.0) + w / (k + rank + 1)
    # 按融合分降序返回列表
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
