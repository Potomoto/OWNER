# app/settings.py
import os

from dotenv import load_dotenv

# 1) 自动加载项目根目录的 .env
# 默认 override=False：如果系统环境变量已设置，就不会被 .env 覆盖（测试里很有用）
load_dotenv()

ENV = os.getenv("ENV", "dev")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./notes.db")
API_KEY = os.getenv("API_KEY")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.siliconflow.cn/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B")

# --- RAG (Week7+) ---
# 将各种可能的true输入都识别成布尔值
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() in ("1", "true", "yes", "y")

# chunk 的大小与 overlap 用 int，后面切分会用到
# overlap 指相邻 chunk 之间重复的部分，避免信息丢失
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "800"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))

# 检索 top_k
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))

# 向量库（第 7-8 周后面会用到），先把配置预留
CHROMA_PATH = os.getenv("CHROMA_PATH", "./.chroma")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "notes_chunks")
