"""语义缓存单测。

刻意**不加载真的 bge 模型**——用假的 embed_query 顶上，所以整个文件毫秒级跑完，
CI 里不会因为下模型而变慢。
"""
import numpy as np
import pytest

from src import config, hybrid_retriever, semantic_cache


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """每个用例都跑在干净的缓存 + 临时落盘路径上。"""
    monkeypatch.setattr(config, "SEMANTIC_CACHE_ENABLED", True)
    monkeypatch.setattr(config, "SEMANTIC_CACHE_THRESHOLD", 0.95)
    monkeypatch.setattr(config, "SEMANTIC_CACHE_PATH", tmp_path / "cache.json")
    semantic_cache.reset()
    yield
    semantic_cache.reset()


def _install_embedder(monkeypatch, mapping):
    """把 embed_query 换成查表，向量按和真实现一样的方式归一化。"""
    def fake(question):
        vec = np.asarray(mapping[question], dtype=np.float32)
        return vec / np.linalg.norm(vec)
    monkeypatch.setattr(semantic_cache, "embed_query", fake)


CHUNKS = [{"text": "片段正文", "source": "resume.md", "score": 1.0}]


def test_empty_cache_is_a_miss(monkeypatch):
    _install_embedder(monkeypatch, {"随便问": [1.0, 0.0]})
    assert semantic_cache.lookup("随便问") == (None, 0.0)


def test_same_question_hits(monkeypatch):
    _install_embedder(monkeypatch, {"介绍一下你自己": [1.0, 0.0]})
    semantic_cache.store("介绍一下你自己", CHUNKS)
    chunks, score = semantic_cache.lookup("介绍一下你自己")
    assert chunks == CHUNKS
    assert score == pytest.approx(1.0, abs=1e-5)


def test_similar_question_hits(monkeypatch):
    """「自我介绍」和「介绍一下你自己」向量很接近 → 应该命中同一条缓存。"""
    _install_embedder(monkeypatch, {
        "介绍一下你自己": [1.0, 0.0],
        "自我介绍": [0.99, 0.141],       # 余弦 ≈ 0.99 > 0.95
    })
    semantic_cache.store("介绍一下你自己", CHUNKS)
    chunks, score = semantic_cache.lookup("自我介绍")
    assert chunks == CHUNKS
    assert score >= 0.95


def test_dissimilar_question_misses(monkeypatch):
    """向量差得远 → 不能命中；但相似度要如实返回，方便日志观察。"""
    _install_embedder(monkeypatch, {
        "介绍一下你自己": [1.0, 0.0],
        "你期望的薪资是多少": [0.0, 1.0],   # 余弦 = 0
    })
    semantic_cache.store("介绍一下你自己", CHUNKS)
    chunks, score = semantic_cache.lookup("你期望的薪资是多少")
    assert chunks is None
    assert score == pytest.approx(0.0, abs=1e-5)


def test_hit_skips_rerank(monkeypatch):
    """命中缓存时，粗召和 rerank 都不该被调用——这才是「省掉 19.6 秒」的证据。"""
    _install_embedder(monkeypatch, {"介绍一下你自己": [1.0, 0.0]})
    semantic_cache.store("介绍一下你自己", CHUNKS)

    called = []
    monkeypatch.setattr(hybrid_retriever, "hybrid_retrieve", lambda *a, **k: called.append("recall") or [])
    monkeypatch.setattr(hybrid_retriever, "rerank", lambda *a, **k: called.append("rerank") or [])

    out = hybrid_retriever.retrieve_with_rerank("介绍一下你自己")
    assert out == CHUNKS
    assert called == []


def test_miss_runs_full_path_and_populates_cache(monkeypatch):
    """未命中时走完整链路，并把结果写进缓存（下一次就该命中了）。"""
    _install_embedder(monkeypatch, {"全新的问题": [1.0, 0.0]})
    monkeypatch.setattr(hybrid_retriever, "hybrid_retrieve",
                        lambda q, top_k: [{"text": "候选", "source": "s"}])
    monkeypatch.setattr(hybrid_retriever, "rerank",
                        lambda q, candidates, top_k: [{"text": "候选", "source": "s", "score": 9.0}])

    out = hybrid_retriever.retrieve_with_rerank("全新的问题")
    assert out[0]["score"] == 9.0
    assert semantic_cache.size() == 1


def test_persistence_roundtrip(monkeypatch):
    """写盘后再读回来，仍然命中——服务重启不该把缓存清空。"""
    _install_embedder(monkeypatch, {"介绍一下你自己": [1.0, 0.0]})
    semantic_cache.store("介绍一下你自己", CHUNKS)

    semantic_cache.reset()
    monkeypatch.setattr(semantic_cache, "_loaded", False)   # 逼它重新读盘

    chunks, _score = semantic_cache.lookup("介绍一下你自己")
    assert chunks == CHUNKS


def test_cache_hit_is_visible_to_the_caller(monkeypatch):
    """last_lookup() 是 chat 日志标注 cache_hit 的来源，必须准。"""
    _install_embedder(monkeypatch, {"介绍一下你自己": [1.0, 0.0]})
    semantic_cache.store("介绍一下你自己", CHUNKS)

    semantic_cache.lookup("介绍一下你自己")
    assert semantic_cache.last_lookup()["hit"] is True

    semantic_cache.reset()
    semantic_cache.lookup("介绍一下你自己")
    assert semantic_cache.last_lookup()["hit"] is False
