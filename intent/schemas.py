"""意图识别结果的数据模型。"""
from pydantic import BaseModel


class IntentResult(BaseModel):
    chart_type: str  # bar / line / pie / table
    confidence: float = 0.0
    keywords: list[str] = []
