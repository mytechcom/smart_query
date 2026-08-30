"""Mock 数据：向电商库插入示例数据，供 NL2SQL 查询演示。

说明：
  - SQL 统一使用 %s 占位符，由 connection.adapt_sql 在 SQLite 模式下转换为 ?
  - 使用 insert_ignore() 保证重复执行幂等
  - 插入顺序遵循外键依赖：categories → users → products → addresses → orders → order_items → reviews
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import insert_ignore  # noqa: E402
from database.connection import adapt_sql  # noqa: E402


def insert_mock_data(cursor) -> None:
    ii = insert_ignore()  # INSERT IGNORE INTO (MySQL) / INSERT OR IGNORE INTO (SQLite)

    # 1. 分类
    categories = [("手机",), ("电脑",), ("配件",), ("家电",)]
    cursor.executemany(
        adapt_sql(f"{ii} categories (name) VALUES (%s)"), categories
    )

    # 2. 用户
    users = [
        ("张三", "zhangsan@test.com"),
        ("李四", "lisi@test.com"),
        ("王五", "wangwu@test.com"),
    ]
    cursor.executemany(
        adapt_sql(f"{ii} users (username, email) VALUES (%s, %s)"), users
    )

    # 3. 商品（category_id 对应 categories 自增 id：1手机 2电脑 3配件 4家电）
    products = [
        ("iPhone 15", 1, 5999.00, "128G"),
        ("iPhone 15 Pro", 1, 7999.00, "256G"),
        ("MacBook Pro", 2, 12999.00, "M3/16G/512G"),
        ("ThinkPad X1", 2, 9999.00, "i7/16G/1T"),
        ("AirPods", 3, 1299.00, "标准版"),
        ("扫地机器人", 4, 2999.00, "LDS导航"),
    ]
    cursor.executemany(
        adapt_sql(f"{ii} products (name, category_id, price, spec) VALUES (%s, %s, %s, %s)"),
        products,
    )

    # 4. 地址
    addresses = [
        (1, "北京市朝阳区xxx", "13800000001"),
        (2, "上海市浦东区xxx", "13800000002"),
        (3, "广州市天河区xxx", "13800000003"),
    ]
    cursor.executemany(
        adapt_sql(f"{ii} addresses (user_id, address, phone) VALUES (%s, %s, %s)"),
        addresses,
    )

    # 5. 订单 + 订单明细（近 7 天，共 30 单）
    import random
    from datetime import datetime, timedelta
    random.seed(42)
    prices = {1: 5999, 2: 7999, 3: 12999, 4: 9999, 5: 1299, 6: 2999}
    for i in range(1, 31):
        days_ago = random.randint(0, 7)
        order_date = datetime.now() - timedelta(days=days_ago)
        order_no = f"ORD{order_date.strftime('%Y%m%d')}{i:04d}"
        user_id = random.choice([1, 2, 3])
        addr_id = random.choice([1, 2, 3])
        product_id = random.choice(list(prices.keys()))
        qty = random.randint(1, 3)
        price = prices[product_id]
        total = qty * price

        cursor.execute(
            adapt_sql(
                f"{ii} orders (order_no, user_id, address_id, total_amount, created_at) "
                f"VALUES (%s, %s, %s, %s, %s)"
            ),
            (order_no, user_id, addr_id, total,
             order_date.strftime("%Y-%m-%d %H:%M:%S")),
        )

        # 取订单 id（兼容 INSERT IGNORE 被忽略的情况）
        cursor.execute(adapt_sql("SELECT id FROM orders WHERE order_no = %s"), (order_no,))
        row = cursor.fetchone()
        if row:
            order_id = row[0]
            cursor.execute(
                adapt_sql(
                    f"{ii} order_items (order_id, product_id, quantity, price) "
                    f"VALUES (%s, %s, %s, %s)"
                ),
                (order_id, product_id, qty, price),
            )

    # 6. 评价
    for _ in range(20):
        cursor.execute(
            adapt_sql(
                f"{ii} reviews (user_id, product_id, rating, comment) VALUES (%s, %s, %s, %s)"
            ),
            (random.choice([1, 2, 3]), random.choice(list(prices.keys())),
             random.randint(3, 5), "商品不错，物流很快！"),
        )

    print("✅ Mock 数据插入完成（30 个订单 / 6 个商品 / 20 条评价）")
