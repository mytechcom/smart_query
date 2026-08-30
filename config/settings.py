"""全局配置：从 .env 读取环境变量，供各模块统一调用。

数据库支持两种模式（由 DB_TYPE 决定）：
  - mysql  （默认，生产推荐）：需 MySQL 服务
  - sqlite （本地免服务）：仅用于快速体验 / 离线验证
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Windows 控制台编码兼容：不强制改编码，仅开启容错，
# 防止 print 输出中文/emoji 时因编码不可表示而抛 UnicodeEncodeError
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

# ==================== 数据库 ====================
DB_TYPE = os.getenv("DB_TYPE", "mysql").strip().lower()

# --- MySQL 配置 ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "ecommerce")

# --- SQLite 配置（DB_TYPE=sqlite 时生效）---
DB_PATH = os.getenv("DB_PATH", "database/ecommerce.db")

# ==================== LLM ====================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# LangChain 开关：默认 True，使用 LangChain 封装调用模型；
# 设为 false 则回退为 openai SDK 直连（两种方式均兼容 DeepSeek）。
USE_LANGCHAIN = os.getenv("USE_LANGCHAIN", "true").strip().lower() in (
    "1", "true", "yes", "on",
)

# ==================== 常量 ====================
CHART_TYPES = ["bar", "line", "pie", "table"]

# SQL 安全校验：仅允许只读 SELECT
ALLOWED_SQL_KEYWORDS = ["select"]
FORBIDDEN_SQL_KEYWORDS = [
    "drop", "delete", "update", "insert",
    "alter", "truncate", "create", "grant", "exec",
]


def placeholder() -> str:
    """当前数据库的参数占位符（MySQL=%s，SQLite=?）。"""
    return "%s" if DB_TYPE == "mysql" else "?"


def insert_ignore() -> str:
    """可忽略重复键的 INSERT 前缀（两种数据库语法不同）。"""
    return "INSERT IGNORE INTO" if DB_TYPE == "mysql" else "INSERT OR IGNORE INTO"


def db_label() -> str:
    """数据库连接描述，用于日志输出。"""
    if DB_TYPE == "mysql":
        return f"mysql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return f"sqlite://{DB_PATH}"
