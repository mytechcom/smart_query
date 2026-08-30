"""表格视图：返回 DataFrame，供 Streamlit / 前端直接渲染。"""
import pandas as pd


def render_table(df: pd.DataFrame, title: str = "") -> pd.DataFrame:
    """返回原始 DataFrame（表格类型无需图表）。"""
    return df
