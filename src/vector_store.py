"""向量数据库：ChromaDB 持久化存储 + 增量同步。"""
import logging

import chromadb

from . import config
from .document_loader import chunk_document
from .embedder import embed_texts

logger = logging.getLogger(__name__)

_client = None


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return _client


def get_collection():
    return get_client().get_or_create_collection(name=config.COLLECTION_NAME)


def _index_items(items):
    """把分块后的条目向量化并写入（upsert 语义，重复写入不报错）。"""
    if not items:
        return
    collection = get_collection()
    ids = [c["id"] for c in items]
    texts = [c["text"] for c in items]
    metadatas = [{"source": c["source"], "file_hash": c["file_hash"]} for c in items]
    embeddings = embed_texts(texts).tolist()
    collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)


def delete_by_source(source: str):
    """删除某个来源文件的所有片段。"""
    get_collection().delete(where={"source": source})


def list_indexed():
    """返回当前已索引的来源及其内容指纹 {source: file_hash}。"""
    collection = get_collection()
    if collection.count() == 0:
        return {}
    data = collection.get(include=["metadatas"])
    result = {}
    for meta in data.get("metadatas", []):
        if meta:
            result[meta.get("source")] = meta.get("file_hash")
    return result


def get_all_chunks():
    """返回所有已索引片段 [{id, text, source}, ...]，供 BM25 建索引用。"""
    collection = get_collection()
    if collection.count() == 0:
        return []
    data = collection.get(include=["documents", "metadatas"])
    chunks = []
    for i, doc_id in enumerate(data.get("ids", [])):
        meta = data.get("metadatas", [])[i] if data.get("metadatas") else None
        chunks.append({
            "id": doc_id,
            "text": data["documents"][i],
            "source": meta.get("source", "未知") if meta else "未知",
        })
    return chunks


def sync_index(docs):
    """增量同步：只处理新增/变化的文档，并清理已删除的文档。返回统计 dict。"""
    indexed = list_indexed()                       # {source: file_hash}
    current = {d["name"]: d for d in docs}

    to_delete = [name for name in indexed if name not in current]          # 文件已删除
    to_upsert = [d for name, d in current.items() if indexed.get(name) != d["file_hash"]]  # 新增或内容变化
    skipped = len([name for name in current if indexed.get(name) == current[name]["file_hash"]])

    for name in to_delete:
        delete_by_source(name)

    added = 0
    updated = 0
    for doc in to_upsert:
        if doc["name"] in indexed:
            updated += 1
            delete_by_source(doc["name"])   # 内容变化：先清旧片段，避免残留
        else:
            added += 1
        _index_items(chunk_document(doc))

    return {"added": added, "updated": updated, "deleted": len(to_delete), "skipped": skipped}


def count_docs():
    """返回已索引的片段数量；向量库读取失败时记录日志并返回 0。"""
    try:
        return get_collection().count()
    except Exception as exc:
        logger.warning("读取向量库片段数量失败：%s", exc)
        return 0
