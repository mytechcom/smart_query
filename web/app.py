"""Streamlit 前端界面。

启动：streamlit run web/app.py --server.port 8501（在项目根目录执行）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402
import requests  # noqa: E402
import pandas as pd  # noqa: E402

from config.logger import logger  # noqa: E402
from visualization.charts import render_bar, render_line, render_pie  # noqa: E402
from visualization.table_view import render_table  # noqa: E402

API_URL = os.getenv("API_URL", "http://localhost:8000/api/query")

st.set_page_config(page_title="智能问数系统", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    .query-title {
        font-size: 1.1rem; font-weight: 600; color: #333;
        border-left: 4px solid #1677ff; padding-left: 0.6rem; margin: 0.4rem 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🧠 智能问数系统")
st.caption("输入自然语言，直接获得可视化图表（如「统计各品类销售额」）")

examples = [
    "统计今天各个品类的销售额",
    "近7天每天的订单总额趋势",
    "各分类商品销售额占比",
    "订单明细列表",
]
st.write("**示例：** " + "　".join(f"`{e}`" for e in examples))

query = st.text_input("请输入你的问题：", placeholder=examples[0])

# ==================== 查询逻辑 ====================
if st.button("查询", type="primary"):
    if not query.strip():
        st.warning("请输入问题")
        st.stop()

    with st.spinner("正在理解问题并生成图表..."):
        try:
            resp = requests.post(API_URL, json={"query": query}, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            logger.info("前端收到响应：query=%r rows=%s", query, data.get("row_count"))
        except requests.exceptions.ConnectionError:
            st.error("无法连接后端 API，请确认 uvicorn 已启动（`uvicorn api.main:app --port 8000`）")
            st.stop()
        except Exception as e:
            st.error(f"请求后端失败：{e}")
            st.stop()

    # 顶部展示：问题 + 结果概览
    st.markdown(f'<div class="query-title">📌 {query}</div>', unsafe_allow_html=True)
    ms = data.get("processing_time_ms")
    row_count = data.get("row_count")
    col_summary = st.columns(3)
    col_summary[0].metric("耗时", f"{ms:.0f} ms" if ms is not None else "-")
    col_summary[1].metric("数据行数", row_count if row_count is not None else "-")
    col_summary[2].metric(
        "图表类型",
        {"bar": "柱状图", "line": "折线图", "pie": "饼图", "table": "表格"}.get(
            data.get("intent", {}).get("chart_type"), "表格"
        ),
    )

    # ==================== 主区域：直接展示图表 ====================
    chart_data = data.get("data", [])
    error = data.get("error", "")

    if error and not chart_data:
        st.error(f"😥 查询失败：{error}")
        st.info("排查建议：请查看后端日志（logs/smart_query.log），确认 API Key、数据库连接是否正常。")
    elif not chart_data:
        st.warning("未查询到数据，请尝试换个问法（例如「统计各品类销售额」）。")
    else:
        df = pd.DataFrame(chart_data)
        chart_type = data.get("intent", {}).get("chart_type", "table")

        try:
            if chart_type == "bar" and len(df.columns) >= 2:
                st.components.v1.html(
                    render_bar(df, query).render_embed(), height=500, scrolling=True
                )
            elif chart_type == "line" and len(df.columns) >= 2:
                st.components.v1.html(
                    render_line(df, query).render_embed(), height=500, scrolling=True
                )
            elif chart_type == "pie" and len(df.columns) >= 2:
                st.components.v1.html(
                    render_pie(df, query).render_embed(), height=500, scrolling=True
                )
            else:
                st.dataframe(render_table(df), use_container_width=True)
                st.caption(f"共 {len(df)} 行 × {len(df.columns)} 列")
        except Exception as e:
            logger.exception("图表渲染失败")
            st.error(f"图表渲染失败：{e}")
            st.dataframe(render_table(df), use_container_width=True)

    # ==================== 调试信息：意图 / SQL（默认折叠） ====================
    with st.expander("🔍 调试信息（意图识别 / SQL / 说明）"):
        method_label = {"llm": "LLM 智能生成", "rule": "规则模板（LLM 不可用）", "failed": "生成失败"}.get(
            data.get("method"), data.get("method") or "-"
        )
        st.markdown(f"**SQL 生成方式：** {method_label}")
        st.json(
            {
                "意图": data.get("intent"),
                "SQL": data.get("sql"),
                "说明": data.get("explanation"),
            }
        )
        st.caption("后端完整日志请查看 logs/smart_query.log")
