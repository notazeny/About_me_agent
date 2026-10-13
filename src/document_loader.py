"""文档读取与分块：支持 .txt / .md / .pdf / .docx。"""
import hashlib
import logging
from pathlib import Path
from . import config

logger = logging.getLogger(__name__)


def _read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_pdf(path: Path) -> str:
    """解析 PDF：逐页抽取正文文本，过滤空页后拼接成一段。"""
    import pdfplumber
    parts = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)


def _read_docx(path: Path) -> str:
    """解析 Word：抽取正文段落，并把表格内容按“ | ”拼接（避免表格信息丢失）。"""
    import docx
    doc = docx.Document(str(path))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def read_file(path: Path) -> str:
    """按扩展名读取单个文档，返回文本。"""
    ext = path.suffix.lower()
    if ext in (".txt", ".md"):   # markdown 按纯文本读
        return _read_txt(path)
    if ext == ".pdf":
        return _read_pdf(path)
    if ext == ".docx":
        return _read_docx(path)
    return ""


def read_documents(docs_dir: Path = config.DOCS_DIR):
    """读取 docs 目录下所有支持的文档，返回 [{name, text, file_hash}, ...]。"""
    docs_dir = Path(docs_dir)
    if not docs_dir.exists():
        return []
    items = []
    for f in sorted(docs_dir.iterdir()):
        if not f.is_file() or f.suffix.lower() not in config.SUPPORTED_EXTENSIONS:
            continue
        try:
            text = read_file(f).strip()
        except Exception as exc:  # 单个文件读取失败不应中断整体
            logger.warning("读取 %s 失败：%s", f.name, exc)
            continue
        if text:
            items.append({
                "name": f.name,
                "text": text,
                "file_hash": hashlib.md5(text.encode("utf-8")).hexdigest(),
            })
    return items


# ---- 递归字符切分 ----
# 分隔符优先级：从「大边界」到「小边界」；最后的 "" 表示「无分隔符可用 → 硬切」
SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]

def _merge(pieces, sep, chunk_size):
    """把相邻短碎片用 sep 拼回，凑近但不超过 chunk_size。"""
    result = []
    cur = ""
    for p in pieces:
        if cur and len(cur) + len(sep) + len(p) > chunk_size:
            result.append(cur)      # 放不下下一个了，结算当前段
            cur = p
        else:
            cur = p if not cur else cur + sep + p
    if cur:
        result.append(cur)
    return result


def _recursive_split(text, separators, chunk_size):
    """递归切分核心：按优先级从高到低使用分隔符，直到文本够短或切不动为止。"""
    # 空串/纯空白返回 []
    if not text or not text.strip():
        return []
    # 够短（len(text) <= chunk_size）就直接返回 [text]
    if len(text) <= chunk_size:
        return [text]
    
    # 取最高优先级分隔符 sep = separators[0]
    sep = separators[0]

    # 若 sep == ""：没有分隔符可用，按 chunk_size 硬切返回
    if sep == "":
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    
    # 否则按 sep 切开（text.split(sep)）
    pieces = text.split(sep)
    result = []
    buffer = []
    # 遍历每段
    for piece in pieces:
        # 空段（not piece.strip()）跳过
        if not piece or not piece.strip():
            continue
        # 段长 <= chunk_size → 放进 buffer（稍后合并）
        if len(piece) <= chunk_size:
            buffer.append(piece)
        # 段长 >  chunk_size → 先 _merge(buffer, sep, chunk_size) 结算进结果，
        # 再对这段用 separators[1:] 递归切（_recursive_split）
        else:
            if buffer:
                result.extend(_merge(buffer, sep, chunk_size))
                buffer = []
            # 递归调用（这里也是运行在“长文本”分支下的）
            result.extend(_recursive_split(piece, separators[1:], chunk_size))

    # 遍历完，把剩余 buffer 也 _merge 结算进结果，最后 return 结果
    if buffer:
        result.extend(_merge(buffer, sep, chunk_size))

    return result


def chunk_text(text, chunk_size=config.CHUNK_SIZE):
    """按自然边界（段落→句子→子句）递归切分，凑近 chunk_size，不切碎句子。"""
    return _recursive_split(text.strip(), SEPARATORS, chunk_size)



def chunk_document(doc, chunk_size: int = config.CHUNK_SIZE):
    """把单个文档切分好，返回 [{id, text, source, file_hash}, ...]。"""
    items = []
    for i, chunk in enumerate(chunk_text(doc["text"], chunk_size)):
        items.append({
            "id": f"{doc['name']}#{i}",
            "text": chunk,
            "source": doc["name"],
            "file_hash": doc["file_hash"],
        })
    return items
