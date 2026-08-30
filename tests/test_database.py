"""数据库初始化测试。

默认 DB_TYPE 为 mysql，测试时强制切到 sqlite 并使用临时文件，
确保不依赖真实 MySQL 服务即可验证建表 + Mock 数据链路。
"""
import os
import sqlite3
import tempfile
from unittest.mock import patch


def test_database_init():
    """验证建表 + Mock 数据可正常插入（SQLite 离线模式）。"""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        with patch("config.settings.DB_TYPE", "sqlite"), \
             patch("config.settings.DB_PATH", db_path):
            from database import init_db
            init_db.init_database()

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders")
            order_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM products")
            product_count = cursor.fetchone()[0]
            conn.close()

            assert order_count > 0, "订单表应有 Mock 数据"
            assert product_count > 0, "商品表应有 Mock 数据"
    print("✅ 数据库初始化测试通过")
