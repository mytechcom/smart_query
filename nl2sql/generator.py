"""NL2SQL 核心引擎：意图识别 → 表结构注入 → LLM 生成 SQL → 校验。"""
import time

from llm.client import chat_json, parse_llm_json
from config.logger import logger
from intent.recognizer import recognize_intent
from intent.schemas import IntentResult
from nl2sql.fallback import build_fallback_sql

# 注入给 LLM 的数据库表结构上下文（数据字典）
TABLE_INFO = """
数据库：MySQL（电商系统）

表结构：
1. categories (商品分类): id, name
2. products (商品): id, name, category_id, price, spec
3. orders (订单): id, order_no, user_id, address_id, total_amount, status, created_at
4. order_items (订单明细): id, order_id, product_id, quantity, price
5. users (用户): id, username, email, created_at
6. addresses (地址): id, user_id, address, phone
7. reviews (评价): id, user_id, product_id, rating, comment, created_at

关键关系（JOIN 条件）：
- products.category_id = categories.id
- order_items.order_id = orders.id
- order_items.product_id = products.id
- orders.user_id = users.id

常用计算：
- 销售额 = SUM(order_items.quantity * order_items.price)
- 今天：DATE(orders.created_at) = CURDATE()
- 近 N 天：orders.created_at >= DATE_SUB(CURDATE(), INTERVAL N DAY)
"""

NL2SQL_SYSTEM = """你是一个 MySQL SQL 生成专家。根据用户自然语言问句，生成 MySQL 查询语句。

【要求】
1. 仅生成一条 SELECT 查询，禁止任何写操作
2. 返回严格 JSON：{{"sql": "SELECT ...", "explanation": "简要说明"}}
3. 涉及"销售额/金额/营收"时，用 SUM(order_items.quantity * order_items.price) 计算
4. 涉及"今天/今日"时用 DATE(orders.created_at) = CURDATE()
5. 涉及"近N天/最近N天"时用 orders.created_at >= DATE_SUB(CURDATE(), INTERVAL N DAY)
6. 结果需适合图表展示：分类列 + 数值列"""


def _build_sql_messages(query: str) -> list:
    """用 LangChain ChatPromptTemplate 构造 NL2SQL 消息（system 注入表结构）。"""
    from langchain_core.prompts import ChatPromptTemplate

    prompt = ChatPromptTemplate.from_messages([
        ("system", NL2SQL_SYSTEM + "\n\n【数据库表结构】\n{table_info}"),
        ("human", "用户问句：{query}"),
    ])
    return prompt.format_messages(table_info=TABLE_INFO, query=query)


def generate_sql(query: str) -> dict:
    """调用 LLM 生成 SQL；失败或结果非法时回落到规则模板。"""
    start = time.perf_counter()
    try:
        messages = _build_sql_messages(query)
        result_str = chat_json(messages)
        data = parse_llm_json(result_str)
        sql = str(data.get("sql", "")).strip()
        explanation = str(data.get("explanation", ""))
        if not sql:
            raise ValueError("LLM 返回空 SQL")
        logger.info(
            "SQL 生成完成（LLM）：query=%r 耗时=%.0fms\nSQL=%s",
            query, (time.perf_counter() - start) * 1000, sql,
        )
        return {"sql": sql, "explanation": explanation, "method": "llm"}
    except Exception as e:
        logger.warning(
            "LLM 生成 SQL 失败（%s: %s），尝试规则兜底", type(e).__name__, e
        )
        fallback_sql = build_fallback_sql(query)
        if fallback_sql:
            return {
                "sql": fallback_sql,
                "explanation": f"LLM 不可用，已使用规则模板生成",
                "method": "rule",
            }
        logger.error(
            "SQL 生成失败：query=%r 耗时=%.0fms 原因=%s: %s",
            query, (time.perf_counter() - start) * 1000, type(e).__name__, e,
            exc_info=True,
        )
        return {"sql": "", "explanation": f"生成失败: {e}", "method": "failed"}


def process_query(query: str) -> dict:
    """完整处理流程：意图识别 → NL2SQL → 返回结构化结果。"""
    intent: IntentResult = recognize_intent(query)
    sql_result = generate_sql(query)
    return {
        "query": query,
        "intent": intent.model_dump(),
        "sql": sql_result.get("sql", ""),
        "explanation": sql_result.get("explanation", ""),
        "method": sql_result.get("method", ""),
    }
