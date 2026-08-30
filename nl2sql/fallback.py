"""规则兜底 SQL 生成器。

当 LLM 不可用（未配置 API Key / 网络异常 / 返回非法 SQL）时，
根据关键词匹配常见查询模板，保证演示环境下「输入 → 图表」的链路依然可跑。
所有 SQL 均为 MySQL 与 SQLite 通用写法。
"""
from config.logger import logger

# 各品类销售额（柱状图 / 饼图通用）
CATEGORY_SALES_SQL = (
    "SELECT c.name AS 品类, SUM(oi.quantity * oi.price) AS 销售额 "
    "FROM categories c "
    "JOIN products p ON p.category_id = c.id "
    "JOIN order_items oi ON oi.product_id = p.id "
    "GROUP BY c.name ORDER BY 销售额 DESC"
)

# 每日销售额趋势（折线图）
DAILY_TREND_SQL = (
    "SELECT DATE(o.created_at) AS 日期, "
    "SUM(oi.quantity * oi.price) AS 销售额 "
    "FROM orders o "
    "JOIN order_items oi ON oi.order_id = o.id "
    "GROUP BY DATE(o.created_at) ORDER BY 日期"
)

# 订单明细（表格）
ORDER_DETAIL_SQL = (
    "SELECT o.order_no AS 订单号, u.username AS 用户, "
    "o.total_amount AS 金额, o.status AS 状态, o.created_at AS 下单时间 "
    "FROM orders o "
    "JOIN users u ON o.user_id = u.id "
    "ORDER BY o.created_at DESC LIMIT 20"
)

_RULES = [
    # (关键词组合匹配, 返回 SQL)
    (lambda q: ("趋势" in q or "走势" in q or "每天" in q or "每日" in q)
              and any(k in q for k in ["销售额", "金额", "营收", "总额", "订单"]),
     DAILY_TREND_SQL),
    (lambda q: "占比" in q or "比例" in q or "份额" in q,
     CATEGORY_SALES_SQL),
    (lambda q: ("品类" in q or "分类" in q) and any(k in q for k in ["销售额", "金额", "营收", "统计", "排行"]),
     CATEGORY_SALES_SQL),
    (lambda q: "明细" in q or "列表" in q or ("所有" in q and "订单" in q),
     ORDER_DETAIL_SQL),
    (lambda q: any(k in q for k in ["销售额", "金额", "营收"]),
     CATEGORY_SALES_SQL),
]


def build_fallback_sql(query: str) -> str:
    """按关键词匹配返回兜底 SQL；无匹配时返回空字符串。"""
    q = query.lower()
    for match, sql in _RULES:
        if match(q):
            logger.info("规则兜底 SQL 命中：query=%r", query)
            return sql
    logger.warning("规则兜底 SQL 未命中任何模板：query=%r", query)
    return ""
