"""纯函数单测：RRF 融合、拒答判定、提示词构造。

这三个是检索/生成链路里**最容易改错、又最容易单测**的部分：

- `weighted_rrf` 的权重或排名公式写错，排序会悄悄变化，线上没人能一眼看出来
- `should_refuse` 的阈值判断反了，要么全拒答、要么全放行
- `build_prompt` 漏掉来源，引用溯源就无从谈起

不加载模型、不连数据库、不调 API，毫秒级。
"""
from __future__ import annotations

import pytest

from src.generator import build_prompt, should_refuse
from src.hybrid_retriever import weighted_rrf

# ============================================================
# weighted_rrf
# ============================================================

def test_rrf_single_list_keeps_order():
    """只有一个列表时，融合结果保持原始排名顺序。"""
    ranked = [("a", 0.9), ("b", 0.8), ("c", 0.7)]
    fused = weighted_rrf(ranked, [], k=60, weights=(1.0, 0.0))
    assert [doc_id for doc_id, _ in fused] == ["a", "b", "c"]


def test_rrf_first_place_uses_k_plus_one():
    """排名从 0 起，第一名得分 = weight / (k + 0 + 1)。"""
    fused = weighted_rrf([("a", 1.0)], [], k=60, weights=(1.0, 0.0))
    assert fused[0][1] == pytest.approx(1.0 / 61)


def test_rrf_overlap_accumulates_scores():
    """同时出现在两个列表里的文档，分数是两边之和。"""
    fused = dict(weighted_rrf([("a", 1.0)], [("a", 1.0)], k=60, weights=(0.5, 0.5)))
    assert fused["a"] == pytest.approx(0.5 / 61 + 0.5 / 61)


def test_rrf_empty_inputs():
    assert weighted_rrf([], []) == []


def test_rrf_weights_change_ranking():
    """提高 BM25 权重后，只出现在 BM25 首位的结果应当反超。"""
    fused = weighted_rrf([("v", 1.0)], [("b", 1.0)], k=60, weights=(0.1, 0.9))
    assert fused[0][0] == "b"


# ============================================================
# should_refuse
# ============================================================

def test_refuse_on_empty_chunks():
    assert should_refuse([], threshold=0.5) is True


def test_refuse_below_threshold():
    assert should_refuse([{"text": "x", "score": 0.2}], threshold=0.5) is True


def test_do_not_refuse_at_threshold():
    """边界值：等于阈值不算低于，应当放行。"""
    assert should_refuse([{"text": "x", "score": 0.5}], threshold=0.5) is False


def test_do_not_refuse_when_score_missing():
    """没有分数信息时交给提示词兜底，不要擅自拒答。"""
    assert should_refuse([{"text": "x"}], threshold=0.5) is False


# ============================================================
# build_prompt
# ============================================================

def _chunks():
    return [
        {"text": "片段一", "source": "portfolio.md"},
        {"text": "片段二", "source": "persona_qa.md"},
        {"text": "片段三", "source": "portfolio.md"},
    ]


def test_prompt_contains_query_and_context():
    p = build_prompt("你做过什么项目？", _chunks())
    assert "你做过什么项目？" in p
    assert "片段一" in p and "片段三" in p


def test_prompt_dedupes_sources_but_keeps_order():
    """来源列表要去重，且保持出现顺序。"""
    p = build_prompt("q", _chunks())
    line = next(ln for ln in p.splitlines() if "引用自" in ln)
    assert line.count("portfolio.md") == 1
    assert "persona_qa.md" in line
    assert line.index("portfolio.md") < line.index("persona_qa.md")


def test_prompt_includes_history_when_given():
    history = [
        {"role": "user", "content": "上一个问题"},
        {"role": "assistant", "content": "上一个回答"},
    ]
    p = build_prompt("新问题", _chunks(), history=history)
    assert "上一个问题" in p and "上一个回答" in p


def test_prompt_without_history_has_no_history_section():
    p = build_prompt("q", _chunks())
    assert "【对话历史】" not in p
