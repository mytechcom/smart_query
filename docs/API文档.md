# API 文档

## POST /api/query
核心查询接口。

**请求体**
```json
{ "query": "统计今天各个品类的销售额" }
```

**响应**
```json
{
  "query": "统计今天各个品类的销售额",
  "intent": {
    "chart_type": "bar",
    "confidence": 0.95,
    "keywords": ["销售额", "品类"]
  },
  "sql": "SELECT c.name, SUM(oi.quantity * oi.price) FROM ... GROUP BY c.name",
  "explanation": "按品类分组统计销售额",
  "columns": ["品类", "销售额"],
  "data": [
    { "品类": "手机", "销售额": 5999 },
    { "品类": "电脑", "销售额": 12999 }
  ]
}
```

## GET /health
健康检查。
```json
{ "status": "ok" }
```
