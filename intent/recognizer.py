"""意图识别：判断用户问句适合用哪种图表展示（bar/line/pie/table）。
优先使用 LLM 结构化输出（LangChain Few-Shot Prompt 模板），
失败时回落到关键词规则，保证离线可跑。
"""
import time

from llm.client import chat_json, parse_llm_json
from config.settings import CHART_TYPES
from config.logger import logger
from intent.schemas import IntentResult

# 规则兜底：关键词 -> 图表类型
KEYWORD_MAP = {
    "line": ["趋势", "变化", "走势", "每天", "每月", "时间", "增长", "下降"],
    "pie": ["占比", "比例", "分布", "百分比", "份额", "构成"],
    "bar": ["统计", "对比", "各", "排行", "top", "最高", "排名"],
    "table": ["明细", "列表", "详情", "所有", "全部", "具体"],
}

# Few-Shot 示例（每类 1 例，覆盖 bar/line/pie/table，符合 D2 示例设计原则）
FEW_SHOT_EXAMPLES = [
    {"query": "统计各品类销售额", "chart_type": "bar",
     "reason": "对比不同品类的高低"},
    {"query": "近7天销售趋势", "chart_type": "line",
     "reason": "描述随时间的变化"},
    {"query": "各品类销售额占比", "chart_type": "pie",
     "reason": "展示占比构成"},
    {"query": "列出全部订单明细", "chart_type": "table",
     "reason": "逐条明细数据"},
]

SYSTEM_PROMPT = """你是一个图表意图识别助手。根据用户自然语言问句，判断最适合的图表类型。
可选类型：bar（柱状图）、line（折线图）、pie（饼图）、table（表格）。
仅返回 JSON：{{"chart_type": "bar", "confidence": 0.95, "keywords": ["销售额", "品类"]}}"""


def _build_intent_messages(query: str) -> list:
    """用 LangChain FewShotChatMessagePromptTemplate 构造意图识别消息。

    返回 BaseMessage 列表，供 llm.client.chat_json 调用。
    """
    from langchain_core.prompts import (
        ChatPromptTemplate,
        FewShotChatMessagePromptTemplate,
    )

    # 示例的输入/输出格式
    example_prompt = ChatPromptTemplate.from_messages([
        ("human", "{query}"),
        ("ai", '{{"chart_type": "{chart_type}", "confidence": 0.95, "keywords": []}}'),
    ])
    few_shot_prompt = FewShotChatMessagePromptTemplate(
        example_prompt=example_prompt,
        examples=FEW_SHOT_EXAMPLES,
    )
    final_prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        few_shot_prompt,
        ("human", "用户问句：{query}"),
    ])
    return final_prompt.format_messages(query=query)


def recognize_intent_rule_based(query: str) -> str:
    """基于关键词的规则兜底。"""
    q = query.lower()
    for chart_type, keywords in KEYWORD_MAP.items():
        if any(kw in q for kw in keywords):
            return chart_type
    return "table"  # 默认表格


def recognize_intent(query: str) -> IntentResult:
    """LLM 意图识别（Few-Shot Prompt），失败则走规则兜底。"""
    start = time.perf_counter()
    try:
        messages = _build_intent_messages(query)
        result_str = chat_json(messages)
        data = parse_llm_json(result_str)
        chart_type = str(data.get("chart_type", "")).strip().lower()
        if chart_type not in CHART_TYPES:
            logger.warning(
                "LLM 返回非法图表类型 %r，回落到规则兜底", chart_type
            )
            chart_type = recognize_intent_rule_based(query)
            method = "rule-fallback"
        else:
            method = "llm"
        result = IntentResult(
            chart_type=chart_type,
            confidence=float(data.get("confidence", 0.5)),
            keywords=data.get("keywords", []),
        )
        logger.info(
            "意图识别完成：query=%r → chart_type=%s confidence=%.2f 来源=%s 耗时=%.0fms",
            query, result.chart_type, result.confidence, method,
            (time.perf_counter() - start) * 1000,
        )
        return result
    except Exception as e:
        logger.warning(
            "LLM 意图识别失败（%s: %s），使用规则兜底", type(e).__name__, e
        )
        result = IntentResult(
            chart_type=recognize_intent_rule_based(query),
            confidence=0.5,
            keywords=[],
        )
        logger.info(
            "意图识别（规则兜底）：query=%r → chart_type=%s",
            query, result.chart_type,
        )
        return result
