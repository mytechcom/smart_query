"""本地验证脚本。

用法：
  python scripts/verify.py           # 默认 SQLite 离线跑通全链路 + 校验 MySQL DDL 语法
  python scripts/verify.py --mysql   # 测试真实 MySQL 连接并初始化（需先配好 .env）

设计说明：
  为避免用户本机尚未安装 MySQL 时无法验证，默认强制使用 SQLite 跑通
  建表 / Mock 数据 / 意图识别 / SQL 校验 / 统计查询 / 图表渲染 整条链路；
  同时对 MySQL DDL 做语法解析校验，确保换成 MySQL 后建表语句同样合法。
"""
import argparse
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def parse_args():
    p = argparse.ArgumentParser(description="智能问数系统 · 本地验证")
    p.add_argument("--mysql", action="store_true", help="测试真实 MySQL 连接并初始化")
    return p.parse_args()


def run_mysql_check():
    """真实 MySQL 模式：测试连接 + 初始化。"""
    import config.settings as settings
    from database.connection import test_connection
    from database.init_db import init_database

    ok, msg = test_connection()
    print(msg)
    if not ok:
        print("提示：请确认 MySQL 已启动，且 .env 中 DB_HOST/DB_PORT/DB_USER/DB_PASSWORD 正确。")
        return
    init_database()
    print("✅ MySQL 模式初始化完成")


def check_mysql_ddl():
    """校验 MySQL DDL 语法（sqlglot 可用时做真实解析，否则做结构检查）。"""
    from database.init_db import MYSQL_SCHEMA

    try:
        import sqlglot
        for ddl in MYSQL_SCHEMA:
            sqlglot.parse_one(ddl, dialect="mysql")
        print(f"✅ [6/6] MySQL DDL 语法解析通过（sqlglot，共 {len(MYSQL_SCHEMA)} 张表）")
        return
    except ImportError:
        pass
    except Exception as e:
        print(f"❌ [6/6] MySQL DDL 语法解析失败：{e}")
        return

    # 未安装 sqlglot 时降级为基础结构检查
    for ddl in MYSQL_SCHEMA:
        clean = ddl.strip().upper()
        assert clean.startswith("CREATE TABLE"), "DDL 应以 CREATE TABLE 开头"
        assert ddl.count("(") == ddl.count(")"), "括号不匹配"
        assert "AUTO_INCREMENT" in clean, "应包含 AUTO_INCREMENT 主键"
    print(f"✅ [6/6] MySQL DDL 结构检查通过（基础模式，共 {len(MYSQL_SCHEMA)} 张表）")
    print("   提示：pip install sqlglot 可做完整 SQL 语法解析")


def run_offline_checks():
    """SQLite 模式离线跑通全链路。"""
    from database.init_db import init_database
    from database.connection import get_connection
    from intent.recognizer import recognize_intent_rule_based
    from nl2sql.validator import validate_sql
    from visualization.charts import render_bar, render_line, render_pie
    from visualization.table_view import render_table

    # [1] 建表 + Mock 数据
    init_database()
    print("✅ [1/6] 数据库建表 + Mock 数据 OK")

    # [2] 数据可读性校验（用真实连接查）
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders")
    assert cur.fetchone()[0] > 0
    cur.execute("SELECT COUNT(*) FROM products")
    assert cur.fetchone()[0] > 0
    print("✅ [2/6] 数据校验 OK（订单/商品表均有数据）")

    # [3] 意图识别（规则兜底，离线可用）
    assert recognize_intent_rule_based("统计各品类销售额") == "bar"
    assert recognize_intent_rule_based("近7天销售额趋势") == "line"
    assert recognize_intent_rule_based("各品类占比") == "pie"
    assert recognize_intent_rule_based("订单明细") == "table"
    print("✅ [3/6] 意图识别 OK（bar/line/pie/table）")

    # [4] SQL 安全校验
    assert validate_sql("SELECT * FROM orders") is True
    assert validate_sql("DROP TABLE orders") is False
    assert validate_sql("DELETE FROM orders") is False
    assert validate_sql("UPDATE orders SET status='1'") is False
    assert validate_sql("SELECT *; DROP TABLE orders") is False
    print("✅ [4/6] SQL 安全校验 OK（拦截写操作与多语句）")

    # [5] 统计 SQL 真实执行（两种库通用写法）
    stats_sql = (
        "SELECT c.name AS 品类, SUM(oi.quantity * oi.price) AS 销售额 "
        "FROM categories c "
        "JOIN products p ON p.category_id = c.id "
        "JOIN order_items oi ON oi.product_id = p.id "
        "GROUP BY c.name"
    )
    assert validate_sql(stats_sql) is True
    cur.execute(stats_sql)
    rows = cur.fetchall()
    conn.close()
    assert len(rows) > 0
    print(f"✅ [5/6] 统计 SQL 执行成功，返回 {len(rows)} 行：{rows}")

    # 图表渲染
    import pandas as pd
    df = pd.DataFrame({"品类": [r[0] for r in rows], "销售额": [r[1] for r in rows]})
    render_bar(df)
    render_line(df)
    render_pie(df)
    render_table(df)

    # [6] MySQL DDL 校验
    check_mysql_ddl()


def main():
    args = parse_args()

    if args.mysql:
        os.environ["DB_TYPE"] = "mysql"
        print("=== 智能问数系统 · MySQL 连接验证 ===\n")
        run_mysql_check()
        return

    # 默认：SQLite 离线全链路验证
    tmpdir = tempfile.mkdtemp()
    os.environ["DB_TYPE"] = "sqlite"
    os.environ["DB_PATH"] = os.path.join(tmpdir, "verify.db")

    import config.settings as settings
    print("=== 智能问数系统 · 本地验证（SQLite 离线模式）===")
    print(f"    目标：{settings.db_label()}\n")
    run_offline_checks()
    print("\n🎉 全部验证通过！")
    print("   · 换成 MySQL 只需修改 .env：DB_TYPE=mysql 并填好连接信息")
    print("   · 验证真实 MySQL：python scripts/verify.py --mysql")


if __name__ == "__main__":
    main()
