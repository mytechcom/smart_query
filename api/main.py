"""FastAPI 后端：提供查询接口。

启动：uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload（在项目根目录执行）
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from config.logger import logger  # noqa: E402
from nl2sql.generator import process_query  # noqa: E402
from nl2sql.executor import execute_sql  # noqa: E402
from nl2sql.fallback import build_fallback_sql  # noqa: E402

app = FastAPI(title="智能问数 API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str


@app.post("/api/query")
def api_query(req: QueryRequest):
    """核心接口：自然语言 → 意图 → SQL → 执行 → 返回数据。"""
    start = time.perf_counter()
    logger.info("收到查询请求：%r", req.query)

    try:
        result = process_query(req.query)

        # 执行 SQL（LLM SQL 校验/执行失败时，自动回落到规则模板重试）
        sql = result.get("sql", "")
        exec_result = execute_sql(sql)
        if not exec_result.get("ok") and result.get("method") == "llm":
            fallback_sql = build_fallback_sql(req.query)
            if fallback_sql:
                logger.warning(
                    "LLM SQL 校验/执行失败（%s），改用规则模板重试：query=%r",
                    exec_result.get("error", "unknown"), req.query,
                )
                fb_result = execute_sql(fallback_sql)
                if fb_result.get("ok"):
                    result["sql"] = fallback_sql
                    result["method"] = "rule"
                    result["explanation"] = "LLM SQL 不可用，已使用规则模板生成"
                    exec_result = fb_result

        if exec_result.get("ok"):
            result["columns"] = exec_result["columns"]
            result["data"] = [
                dict(zip(exec_result["columns"], row))
                for row in exec_result["rows"]
            ]
            result["row_count"] = len(exec_result["rows"])
        else:
            result["columns"] = []
            result["data"] = []
            result["row_count"] = 0
            result["error"] = exec_result.get("error", "")
            logger.warning(
                "查询执行失败：query=%r error=%s", req.query, result["error"]
            )

        result["processing_time_ms"] = round(
            (time.perf_counter() - start) * 1000, 1
        )
        logger.info(
            "查询完成：query=%r chart_type=%s rows=%d 总耗时=%.0fms",
            req.query,
            result.get("intent", {}).get("chart_type", "N/A"),
            result.get("row_count", 0),
            result["processing_time_ms"],
        )
        return result

    except Exception as e:
        logger.exception("查询接口异常：query=%r", req.query)
        return {
            "query": req.query,
            "intent": {},
            "sql": "",
            "explanation": "",
            "columns": [],
            "data": [],
            "row_count": 0,
            "error": f"服务内部错误：{e}",
            "processing_time_ms": round((time.perf_counter() - start) * 1000, 1),
        }


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
