"""NL2SQL 核心引擎：意图识别 → LLM 生成 SQL → 质量校验 → 打回重生成 → 执行。

流程亮点（LangChain 核心价值落地）：
  - 生成结果先过「安全校验 + 试执行」两道质量关；
  - 不合格就把错误信息反馈给 LLM，让它"看着错误自己修正"（自校正循环）；
  - 全部轮次失败才降级到规则模板，保证任何情况下都能给出答案。
"""
import time

from llm.client import chat_json, parse_llm_json
from config.logger import logger
from config.settings import SQL_MAX_ATTEMPTS
from intent.recognizer import recognize_intent
from intent.schemas import IntentResult
from nl2sql.fallback import build_fallback_sql
from nl2sql.validator import validate_sql
from nl2sql.executor import execute_sql

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


def _build_sql_messages(query: str, feedback: str = "") -> list:
    """用 LangChain ChatPromptTemplate 构造 NL2SQL 消息（system 注入表结构）。

    feedback 非空时，作为一条 human 消息追加给 LLM，
    让模型"看着上一轮的报错，自己修正"——这是自校正循环的关键。
    """
    from langchain_core.prompts import ChatPromptTemplate

    parts = [
        ("system", NL2SQL_SYSTEM + "\n\n【数据库表结构】\n{table_info}"),
        ("human", "用户问句：{query}"),
    ]
    if feedback:
        parts.append(("human", feedback))
    prompt = ChatPromptTemplate.from_messages(parts)
    return prompt.format_messages(table_info=TABLE_INFO, query=query)


def _validate_sql_quality(sql: str) -> tuple[bool, str]:
    """SQL 质量两道校验关：安全校验 + 真实试执行。

    返回 (是否通过, 未通过时的具体原因)。执行校验是"真打回"的关键：
    语法/表名/列名/表关系不对，试执行会当场报错，成为反馈给 LLM 的依据。
    """
    if not validate_sql(sql):
        return False, "SQL 未通过安全校验（必须是单条只读 SELECT，禁止写操作）"
    exec_result = execute_sql(sql)
    if not exec_result.get("ok"):
        return False, f"SQL 执行报错：{exec_result.get('error')}"
    return True, ""


def generate_sql(query: str) -> dict:
    """LLM 生成 SQL → 质量校验 → 不合格打回重生成（最多 SQL_MAX_ATTEMPTS 轮）。

    全部轮次仍失败时回落到规则模板；规则也不可用则返回 failed。
    """
    start = time.perf_counter()
    feedback = ""  # 上一轮的错误反馈，注入下一轮 prompt
    last_error = ""

    for attempt in range(1, SQL_MAX_ATTEMPTS + 1):
        try:
            messages = _build_sql_messages(query, feedback)
            result_str = chat_json(messages)
            data = parse_llm_json(result_str)
            sql = str(data.get("sql", "")).strip()
            explanation = str(data.get("explanation", ""))
            if not sql:
                raise ValueError("LLM 返回空 SQL")

            # ---- 质量校验：不合格就把原因打回给 LLM ----
            ok, err = _validate_sql_quality(sql)
            if ok:
                logger.info(
                    "SQL 生成+校验通过：query=%r 尝试%d次 耗时=%.0fms\nSQL=%s",
                    query, attempt, (time.perf_counter() - start) * 1000, sql,
                )
                return {
                    "sql": sql,
                    "explanation": explanation,
                    "method": "llm",
                    "attempts": attempt,
                    "self_corrected": attempt > 1,
                }

            last_error = err
            logger.warning(
                "SQL 质量校验不通过（第 %d/%d 次）：%s\nSQL=%s",
                attempt, SQL_MAX_ATTEMPTS, err, sql,
            )
            feedback = (
                f"【校验反馈】第 {attempt} 次生成的 SQL 有问题，请修正后重新生成。\n"
                f"问题：{err}\n上一次的 SQL：{sql}"
            )
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            logger.warning(
                "LLM 生成 SQL 异常（第 %d/%d 次）：%s",
                attempt, SQL_MAX_ATTEMPTS, last_error,
            )
            feedback = (
                f"【校验反馈】第 {attempt} 次生成失败：{last_error}，请重试。"
            )

    # ---- 全部轮次失败 → 规则模板兜底 ----
    fallback_sql = build_fallback_sql(query)
    if fallback_sql:
        logger.info(
            "SQL 自校正后仍失败（%s），降级规则模板：query=%r",
            last_error, query,
        )
        return {
            "sql": fallback_sql,
            "explanation": "LLM 生成 SQL 校验未通过，已使用规则模板生成",
            "method": "rule",
            "attempts": SQL_MAX_ATTEMPTS,
            "self_corrected": False,
        }
    logger.error(
        "SQL 生成失败（LLM 与规则均不可用）：query=%r 耗时=%.0fms 原因=%s",
        query, (time.perf_counter() - start) * 1000, last_error,
        exc_info=True,
    )
    return {
        "sql": "", "explanation": f"生成失败: {last_error}", "method": "failed",
        "attempts": SQL_MAX_ATTEMPTS, "self_corrected": False,
    }


def process_query(query: str) -> dict:
    """完整处理流程：意图识别 → NL2SQL（含质量校验与自校正）→ 返回结构化结果。"""
    intent: IntentResult = recognize_intent(query)
    sql_result = generate_sql(query)
    return {
        "query": query,
        "intent": intent.model_dump(),
        "sql": sql_result.get("sql", ""),
        "explanation": sql_result.get("explanation", ""),
        "method": sql_result.get("method", ""),
        "attempts": sql_result.get("attempts", 1),
        "self_corrected": sql_result.get("self_corrected", False),
    }
