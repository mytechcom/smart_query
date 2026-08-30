"""数据库初始化：创建 7 张电商表 + 插入 Mock 数据。

默认 MySQL（生产推荐），也支持 SQLite（DB_TYPE=sqlite，本地免服务体验）。
MySQL 模式下会自动创建数据库（若不存在）。

运行方式（二选一，均已处理好导入路径）：
  python database/init_db.py      # 直接运行本脚本
  python -m database.init_db      # 以模块方式运行（需在项目根目录）
"""
import os
import sys

# 关键：把项目根目录加入 sys.path，确保 `import config` / `from database import ...`
# 在「直接运行本脚本」时也能正常工作（此时 sys.path[0] 是 database/ 目录）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config.settings as settings  # noqa: E402
from database.connection import get_connection  # noqa: E402
from database.mock_data import insert_mock_data  # noqa: E402


# ==================== MySQL DDL ====================
MYSQL_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS categories (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '分类ID',
        name VARCHAR(50) NOT NULL COMMENT '分类名称'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品分类表'
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
        username VARCHAR(50) NOT NULL COMMENT '用户名',
        email VARCHAR(100) COMMENT '邮箱',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表'
    """,
    """
    CREATE TABLE IF NOT EXISTS products (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '商品ID',
        name VARCHAR(100) NOT NULL COMMENT '商品名称',
        category_id INT COMMENT '分类ID',
        price DECIMAL(10,2) COMMENT '单价',
        spec VARCHAR(100) COMMENT '规格',
        FOREIGN KEY (category_id) REFERENCES categories(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表'
    """,
    """
    CREATE TABLE IF NOT EXISTS addresses (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '地址ID',
        user_id INT COMMENT '用户ID',
        address VARCHAR(255) COMMENT '详细地址',
        phone VARCHAR(20) COMMENT '联系电话',
        FOREIGN KEY (user_id) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收货地址表'
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '订单ID',
        order_no VARCHAR(50) UNIQUE NOT NULL COMMENT '订单号',
        user_id INT COMMENT '用户ID',
        address_id INT COMMENT '地址ID',
        total_amount DECIMAL(10,2) COMMENT '订单总额',
        status VARCHAR(20) DEFAULT 'completed' COMMENT '订单状态',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '下单时间',
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (address_id) REFERENCES addresses(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表'
    """,
    """
    CREATE TABLE IF NOT EXISTS order_items (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '明细ID',
        order_id INT COMMENT '订单ID',
        product_id INT COMMENT '商品ID',
        quantity INT COMMENT '购买数量',
        price DECIMAL(10,2) COMMENT '成交单价',
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单明细表'
    """,
    """
    CREATE TABLE IF NOT EXISTS reviews (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '评价ID',
        user_id INT COMMENT '用户ID',
        product_id INT COMMENT '商品ID',
        order_id INT COMMENT '订单ID',
        rating INT COMMENT '评分1-5',
        comment TEXT COMMENT '评价内容',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '评价时间',
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评价表'
    """,
]


# ==================== SQLite DDL（本地备用）====================
SQLITE_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(50) NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(50) NOT NULL,
        email VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        category_id INTEGER,
        price DECIMAL(10,2),
        spec VARCHAR(100))""",
    """CREATE TABLE IF NOT EXISTS addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        address VARCHAR(255),
        phone VARCHAR(20))""",
    """CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no VARCHAR(50) UNIQUE NOT NULL,
        user_id INTEGER,
        address_id INTEGER,
        total_amount DECIMAL(10,2),
        status VARCHAR(20) DEFAULT 'completed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        price DECIMAL(10,2))""",
    """CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        order_id INTEGER,
        rating INTEGER,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
]


def _ensure_mysql_database():
    """MySQL 模式下自动创建数据库（若不存在）。"""
    import pymysql
    conn = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        charset="utf8mb4",
    )
    try:
        cur = conn.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` "
            f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
        )
        conn.commit()
    finally:
        conn.close()


def create_tables(cursor):
    """根据 DB_TYPE 执行建表语句。"""
    schema = MYSQL_SCHEMA if settings.DB_TYPE == "mysql" else SQLITE_SCHEMA
    for ddl in schema:
        cursor.execute(ddl)


def init_database():
    """建库（MySQL）→ 建表 → 插入 Mock 数据。"""
    if settings.DB_TYPE == "mysql":
        _ensure_mysql_database()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        create_tables(cursor)
        insert_mock_data(cursor)
        conn.commit()
        print(f"✅ 数据库初始化完成（{settings.db_label()}）")
        print("   已创建 7 张表：categories, users, products, addresses, orders, order_items, reviews")
    finally:
        conn.close()


if __name__ == "__main__":
    init_database()
