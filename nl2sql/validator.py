"""SQL 安全校验：仅允许只读 SELECT，防止删库/注入。

注意：使用「单词边界」匹配危险关键字，避免误杀合法列名
（如 created_at 中含 "create"、updated_at 中含 "update"）。
"""
import re

from config.settings import ALLOWED_SQL_KEYWORDS, FORBIDDEN_SQL_KEYWORDS


def validate_sql(sql: str) -> bool:
    stripped = sql.strip()
    if not stripped:
        return False
    lowered = stripped.lower()

    # 必须以允许的查询关键字开头（忽略多余空白）
    if not any(lowered.startswith(kw) for kw in ALLOWED_SQL_KEYWORDS):
        return False

    # 去掉末尾分号后再检查（LLM 常以 ; 结尾，允许单个尾部 ;）
    core = lowered.rstrip(";").strip()
    if not core:
        return False
    if ";" in core:
        return False  # 多条语句拼接 / 中途分号

    # 危险关键字：单词边界匹配（created_at 中的 create 不会命中）
    for kw in FORBIDDEN_SQL_KEYWORDS:
        if re.search(rf"\b{kw}\b", core):
            return False

    return True
