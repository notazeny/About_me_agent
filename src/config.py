"""About_Me_Agent 项目配置：路径、向量化模型、分块/检索参数、DeepSeek、persona 插槽、MySQL。"""
import os
from pathlib import Path

# ---- 路径 ----
BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "data" / "docs"              # 待索引的非隐私语料（简历/portfolio/项目 README）
CHROMA_DIR = BASE_DIR / "chroma_db"                # 向量库持久化目录
DB_PATH = BASE_DIR / "data" / "sessions.db"        # 旧 SQLite 会话库（已迁移到 MySQL，保留备用）
PERSONA_DIR = BASE_DIR / "data" / "persona"        # 分身插槽目录（风格画像）
PERSONA_STYLE_FILE = PERSONA_DIR / "persona_style.md"   # sazeny 风格画像 → 进 system prompt（Phase 0 填）
PERSONA_QA_FILE = DOCS_DIR / "persona_qa.md"            # sazeny 原话 QA 对 → 进语料被检索（Phase 0 填）


def _load_dotenv(path: Path):
    """极简 .env 读取：把 KEY=VALUE 写入环境变量（已存在的环境变量不覆盖）。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")

# ---- MySQL 连接（从 SQLite 迁移而来）----
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "aboutme")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")        # 敏感，放 .env
MYSQL_DB = os.getenv("MYSQL_DB", "about_me_agent")
# SQLAlchemy 连接串：mysql+pymysql 驱动，utf8mb4 存中文/emoji。
# 可用 DATABASE_URL 环境变量整体覆盖——测试时指向 SQLite，就不必依赖真 MySQL。
DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
)

# ---- JWT 鉴权 ----
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")   # 签名密钥，放 .env（务必随机 + 保密）
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24                              # token 有效期（小时）

# ---- 向量化模型 ----
# BGE 中文小模型：约 100MB、下载快、中文检索效果好；query 需叠前缀（非对称模型）。
EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："

# ---- 分块参数 ----
CHUNK_SIZE = 500      # 每个片段最多字符数

# ---- 检索参数 ----
TOP_K = 3             # 每次检索最相关的片段数量

# ---- 混合检索参数 ----
HYBRID_RECALL_N = 20        # 粗召：向量和 BM25 各自取 top-N，再融合
RRF_K = 60                  # RRF 平滑常数（防除零、抑制第一名权重过大）
HYBRID_WEIGHTS = (0.7, 0.3) # (向量权重, BM25 权重)：语义为主、关键词兜底

# ---- 重排参数 ----
RERANK_MODEL = "BAAI/bge-reranker-base"    # 交叉编码器 rerank 模型（中文）
RERANK_CANDIDATE_N = 10                    # 粗召融合后取多少条候选交给 rerank 精排
RERANK_CONFIDENCE_THRESHOLD = -100.0       # rerank 是 logits（有正有负），0.0 会误拒相关片段；设很低，MVP 只靠「检索为空」+ prompt 兜底诚实拒答

# ---- 语义缓存 ----
# 把「问题 → 检索片段」缓存起来，命中就跳过 rerank（端到端 24s → 约 1.2s）。
# 为什么缓存的是检索而不是最终答案，见 src/semantic_cache.py 顶部注释；
# 取舍与验收指标见 learn+/性能优化待办.md。
SEMANTIC_CACHE_ENABLED = os.getenv("SEMANTIC_CACHE_ENABLED", "1") != "0"
# 相似度阈值：调高 = 更保守（少误命中、少命中）；调低 = 更激进。
# 用 scripts/cache_hitrate.py 扫出来再定，别拍脑袋。
SEMANTIC_CACHE_THRESHOLD = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.95"))
# 落盘位置。标定脚本会把它指到临时文件，避免污染线上缓存。
SEMANTIC_CACHE_PATH = Path(os.getenv("SEMANTIC_CACHE_PATH") or (BASE_DIR / "data" / "semantic_cache.json"))


# ---- 多轮对话 ----
MAX_HISTORY_TURNS = 5   # 生成回答时，带入最近几轮对话作为上下文

# ---- 支持的文档类型 ----
# 语料多为 markdown（portfolio.md / resume.md / README.md），故加入 .md，按纯文本读取
SUPPORTED_EXTENSIONS = (".txt", ".md", ".pdf", ".docx")

# ---- DeepSeek 大模型 ----
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"   # 便宜 flash 模型，公开网站防刷省钱
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# ---- 生成参数 ----
TEMPERATURE = 0.3          # 回答随机性：越低越稳定保守
REQUEST_TIMEOUT = 60       # DeepSeek 请求超时秒数

# ---- 限流（公开网站防刷） ----
RATE_LIMIT_PER_MINUTE = 10   # 每 IP 每分钟最多提问次数
RATE_LIMIT_PER_DAY = 100     # 每 IP 每天最多提问次数

# ---- 向量库集合名 ----
COLLECTION_NAME = "about_me"   # 独立集合，不跟 RAG 项目的 job_knowledge 混

# ---- 前端导航链接（待 sazeny 确认）----
GITHUB_URL = "https://github.com/notazeny"
GITEE_URL = "https://gitee.com/sazeny"
