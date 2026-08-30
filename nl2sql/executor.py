"""SQL 执行器：校验通过后查询数据库，返回 {columns, rows}。

兼容 MySQL 与 SQLite（由 database.connection 统一处理）。
"""
import time

from database.connection import get_connection
from config.logger import logger
from nl2sql.validator import validate_sql


def execute_sql(sql: str) -> dict:
    """执行合法 SQL，返回 {ok, columns, rows} 或 {ok: False, error}。"""
    if not validate_sql(sql):
        logger.warning("SQL 未通过安全校验，已拦截：%r", sql)
        return {"ok": False, "error": "SQL 未通过安全校验（仅允许只读 SELECT）"}

    conn = None
    start = time.perf_counter()
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        logger.info(
            "SQL 执行成功：%d 行，耗时=%.0fms\nSQL=%s",
            len(rows), (time.perf_counter() - start) * 1000, sql,
        )
        return {"ok": True, "columns": columns, "rows": rows}
    except Exception as e:
        logger.error(
            "SQL 执行失败：%s: %s 耗时=%.0fms\nSQL=%s",
            type(e).__name__, e, (time.perf_counter() - start) * 1000, sql,
            exc_info=True,
        )
        return {"ok": False, "error": str(e)}
    finally:
        if conn:
            conn.close()
