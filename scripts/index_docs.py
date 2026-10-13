"""建库脚本：把 data/docs/ 里的语料分块、向量化、写入 ChromaDB。

用法：python scripts/index_docs.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.document_loader import read_documents
from src.vector_store import sync_index, count_docs


def main():
    docs = read_documents()
    if not docs:
        print("data/docs/ 里没有可索引的语料（支持 .txt/.md/.pdf/.docx）")
        return
    stats = sync_index(docs)
    print("建库完成：", stats)
    print("当前向量库片段数：", count_docs())


if __name__ == "__main__":
    main()
