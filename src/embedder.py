"""向量化：用本地 BGE 模型把文本转成向量。"""
from sentence_transformers import SentenceTransformer
from . import config

_model = None


def get_model():
    """懒加载：第一次调用时才下载/加载模型，避免程序启动变慢。"""
    global _model
    if _model is None:
        _model = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
    return _model


def embed_texts(texts):
    """批量向量化（用于文档片段），返回 numpy 数组。

    向量化 = 把一段文字变成一串数字，这样就能用「数字距离」比较两段文字像不像。
    """
    return get_model().encode(list(texts), normalize_embeddings=True)


def embed_query(query: str):
    """向量化单个问题，返回一维向量。

    BGE 模型建议给问题加固定前缀（QUERY_INSTRUCTION），能提高检索命中率。
    """
    return get_model().encode([config.QUERY_INSTRUCTION + query], normalize_embeddings=True)[0]
