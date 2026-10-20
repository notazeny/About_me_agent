"""混合检索：向量粗召 + BM25 粗召 → 加权 RRF 融合 → top-k。"""
import time

from . import config, semantic_cache
from .bm25 import BM25, tokenize
from .embedder import embed_query, get_model

# weighted_rrf 住在 fusion.py（纯函数、零重依赖）。
# 这里 re-export，是为了让老的 `from src.hybrid_retriever import weighted_rrf` 继续可用。
from .fusion import weighted_rrf
from .reranker import get_reranker, rerank
from .vector_store import count_docs, get_all_chunks, get_collection

# 模块级缓存：BM25 索引建一次复用，避免每次查询重建
_chunks = None   # [{id, text, source}]
_bm25 = None


def _load():
    """惰性加载：首次调用从向量库读全部片段、建 BM25 索引。"""
    global _chunks, _bm25
    if _chunks is None:
        _chunks = get_all_chunks()
        _bm25 = BM25([tokenize(c["text"]) for c in _chunks])
    return _chunks, _bm25


def vector_search(query, top_n=config.HYBRID_RECALL_N):
    """向量粗召：返回 [(id, distance)]，distance 越小越相关（已按距离升序）。"""
    collection = get_collection()
    query_vec = embed_query(query).tolist()
    res = collection.query(query_embeddings=[query_vec], n_results=top_n)
    ids = res.get("ids", [[]])[0]
    dists = res.get("distances", [[]])[0]
    return list(zip(ids, dists))


def bm25_search(query, top_n=config.HYBRID_RECALL_N):
    """BM25 粗召：返回 [(id, score)]，score 越大越相关（已按分数降序）。"""
    chunks, bm25 = _load()
    scores = bm25.score(tokenize(query))
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [(chunks[i]["id"], scores[i]) for i in order[:top_n]]


def hybrid_retrieve(query, top_k=config.TOP_K):
    """主入口：向量 + BM25 粗召 → RRF 融合 → 返回 top_k 个 [{text, source, score}]。"""
    # 调用 vector_search / bm25_search / weighted_rrf 三步
    vector_results = vector_search(query)
    bm25_results = bm25_search(query)
    fused = weighted_rrf(vector_results, bm25_results)
    # 取 top_k，用 _load() 拿 _chunks 建 {id: chunk}，映射回 text/source
    chunks, _ = _load()
    id_to_chunk = {c["id"]: c for c in chunks}
    top_items = []
    for doc_id, score in fused[:top_k]:
        if doc_id in id_to_chunk:
            chunk = id_to_chunk[doc_id]
            top_items.append({
                "text": chunk["text"],
                "source": chunk["source"],
                "score": score
            })
    return top_items


def retrieve_with_rerank(query, top_k=config.TOP_K):
    """完整链路：**语义缓存** → 粗召(向量+BM25) → RRF 融合 → rerank 精排 → top_k。

    缓存只包在**检索**这一层：命中就跳过粗召和 rerank（端到端 24s → 约 1.2s）。
    注意**不跳过生成**——答案不缓存，原因见 src/semantic_cache.py 顶部。
    """
    cached, _score = semantic_cache.lookup(query)
    if cached is not None:
        return cached                       # 命中：19.6 秒的 rerank 省掉

    candidates = hybrid_retrieve(query, top_k=config.RERANK_CANDIDATE_N)
    results = rerank(query, candidates, top_k=top_k)
    semantic_cache.store(query, results)    # 首次算完就记住，下次直接给
    return results


def warm_up():
    """预热：把检索链路上「第一次调用才加载」的重家伙全部提前拉起来。

    **不预热会怎样**：这笔开销会落在**重启后的第一个访客**头上——
    线上实测约 13 秒（分词器 + bge-small 向量模型 + bge-reranker-base 交叉编码器
    + BM25 建索引），叠加正常的一次 rerank（约 20 秒），第一个人要盯着空白等 **35 秒**。
    后面的人却只要 1-2 秒。**凭什么让第一个访客买单？**

    **代价（有意的）**：进程要等它就绪才开始接受请求，即**启动变慢约 25 秒**。
    这个取舍是对的——「启动完成」就该等于「真的能用」，
    否则健康检查会放行一个「起来了、但一问就卡 35 秒」的服务，
    而那正是「绿的但坏的」中最难查的一种。

    返回各步骤耗时，供启动日志记录（部署后 grep `startup.warmup` 就能看到）。
    """
    timings = {}
    t0 = time.perf_counter()

    if not count_docs():
        timings["note"] = "向量库为空，跳过预热"
        timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return timings

    for name, load in (
        ("bm25", _load),             # 从向量库读全部片段 + 建 BM25 索引
        ("embedder", get_model),     # bge-small 向量模型
        ("reranker", get_reranker),  # bge-reranker-base 交叉编码器（最重的那个）
    ):
        t = time.perf_counter()
        try:
            load()
        except Exception as exc:
            # 预热失败不该让服务起不来——那会变成 crash loop（Restart=always），
            # 比「起来了但慢」更糟。记下来，让它显式可见。
            timings[name] = f"失败: {exc}"
            continue
        timings[f"{name}_ms"] = round((time.perf_counter() - t) * 1000, 1)

    timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return timings


def warm_state() -> dict:
    """报告预热到底成没成——模型/索引加载了没有。

    给 `/healthz` 用。理由和那个接口的其它检查一样：
    **「服务起来了」不等于「服务能用」**。预热失败时进程照样活着、
    数据库和向量库也照样能连，但每一问都会卡或报错——
    这正是健康检查最该抓住的「绿的但坏的」。

    注意：这里的写法是「取模块属性」而不是 `from .embedder import _model`——
    后者拿到的是**导入那一刻的副本**，之后模块里把它赋值成模型对象，
    这里也不会跟着变，会永远读到 None。
    """
    from . import embedder, reranker

    return {
        "bm25": _chunks is not None,
        "embedder": embedder._model is not None,
        "reranker": reranker._reranker is not None,
    }
