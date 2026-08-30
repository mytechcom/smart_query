"""统一数据库连接层：屏蔽 MySQL 与 SQLite 的差异。

对外提供：
  get_connection()      获取数据库连接
  adapt_sql(sql)        把标准 %s 占位符转换为当前数据库的写法
  test_connection()     测试连通性

路径说明：顶部 sys.path 引导保证本文件被直接运行或作为子模块导入时，
都能找到项目根目录下的 config 包。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config.settings as settings  # noqa: E402


def get_connection():
    """根据 DB_TYPE 返回数据库连接。"""
    if settings.DB_TYPE == "mysql":
        import pymysql
        return pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            charset="utf8mb4",
            autocommit=False,
        )

    import sqlite3
    return sqlite3.connect(settings.DB_PATH)


def adapt_sql(sql: str) -> str:
    """SQLite 模式下把 %s 占位符转换为 ?（MySQL 原样返回）。"""
    if settings.DB_TYPE == "mysql":
        return sql
    return sql.replace("%s", "?")


def test_connection() -> tuple:
    """测试数据库连接，返回 (是否成功, 提示信息)。"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        return True, f"✅ 数据库连接成功（{settings.db_label()}）"
    except Exception as e:
        return False, f"❌ 数据库连接失败（{settings.db_label()}）：{e}"
