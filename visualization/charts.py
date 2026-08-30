"""PyECharts 可视化渲染：柱状图、折线图、饼图。

约定：取数据前两列作为「分类列 + 数值列」。
"""
import pandas as pd
from pyecharts.charts import Bar, Line, Pie
from pyecharts import options as opts

# 统一配色
PALETTE = ["#1677ff", "#52c41a", "#faad14", "#f5222d", "#722ed1", "#13c2c2", "#eb2f96"]

# 分类数量超过该值，自动倾斜标签 + 开启数据缩放
_AXIS_LIMIT = 8


def _split_xy(df: pd.DataFrame) -> tuple:
    """取前两列作为分类列与数值列。"""
    if len(df.columns) < 2:
        raise ValueError("图表至少需要两列数据（分类列 + 数值列）")
    return df.columns[0], df.columns[1]


def _axis_opts(x_col: str, y_col: str, x_categories: list[str]):
    """统一的坐标轴样式：长分类名自动倾斜 + 数量多时开启缩放。"""
    rotate = 30 if len(x_categories) > _AXIS_LIMIT else 0
    return opts.AxisOpts(
        axislabel_opts=opts.LabelOpts(rotate=rotate, interval=0, font_size=12),
    ), opts.AxisOpts(name=y_col)


def render_bar(df: pd.DataFrame, title: str = "") -> Bar:
    """柱状图。"""
    x_col, y_col = _split_xy(df)
    x_categories = df[x_col].astype(str).tolist()
    values = df[y_col].tolist()
    x_axis, y_axis = _axis_opts(x_col, y_col, x_categories)

    bar = (
        Bar()
        .add_xaxis(x_categories)
        .add_yaxis(
            y_col,
            values,
            color=PALETTE[0],
            itemstyle_opts=opts.ItemStyleOpts(border_radius=[4, 4, 0, 0]),
            label_opts=opts.LabelOpts(is_show=False),
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(title=title or y_col),
            tooltip_opts=opts.TooltipOpts(trigger="axis"),
            xaxis_opts=x_axis,
            yaxis_opts=y_axis,
            legend_opts=opts.LegendOpts(is_show=False),
        )
    )
    if len(x_categories) > _AXIS_LIMIT:
        bar.set_global_opts(
            datazoom_opts=[opts.DataZoomOpts(type_="inside"), opts.DataZoomOpts()]
        )
    return bar


def render_line(df: pd.DataFrame, title: str = "") -> Line:
    """折线图。"""
    x_col, y_col = _split_xy(df)
    x_categories = df[x_col].astype(str).tolist()
    values = df[y_col].tolist()
    x_axis, y_axis = _axis_opts(x_col, y_col, x_categories)

    line = (
        Line()
        .add_xaxis(x_categories)
        .add_yaxis(
            y_col,
            values,
            color=PALETTE[0],
            is_smooth=True,
            is_symbol_show=False,
            label_opts=opts.LabelOpts(is_show=False),
            linestyle_opts=opts.LineStyleOpts(width=3),
            areastyle_opts=opts.AreaStyleOpts(opacity=0.12, color=PALETTE[0]),
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(title=title or y_col),
            tooltip_opts=opts.TooltipOpts(trigger="axis"),
            xaxis_opts=x_axis,
            yaxis_opts=y_axis,
            legend_opts=opts.LegendOpts(is_show=False),
        )
    )
    if len(x_categories) > _AXIS_LIMIT:
        line.set_global_opts(
            datazoom_opts=[opts.DataZoomOpts(type_="inside"), opts.DataZoomOpts()]
        )
    return line


def render_pie(df: pd.DataFrame, title: str = "") -> Pie:
    """饼图：超过 8 类时合并为「其他」。"""
    x_col, y_col = _split_xy(df)
    raw = list(zip(df[x_col].astype(str).tolist(), df[y_col].tolist()))

    # 类别过多时折叠尾部为「其他」
    data_pair = raw[:_AXIS_LIMIT]
    if len(raw) > _AXIS_LIMIT:
        rest = sum(v for _, v in raw[_AXIS_LIMIT:])
        data_pair.append(("其他", rest))

    return (
        Pie()
        .add(
            "",
            data_pair,
            radius=["35%", "70%"],
            label_opts=opts.LabelOpts(formatter="{b}: {c} ({d}%)"),
            itemstyle_opts=opts.ItemStyleOpts(border_color="#fff", border_width=1),
        )
        .set_colors(PALETTE)
        .set_global_opts(
            title_opts=opts.TitleOpts(title=title or y_col),
            tooltip_opts=opts.TooltipOpts(trigger="item", formatter="{b}: {c} ({d}%)"),
            legend_opts=opts.LegendOpts(type_="scroll", pos_top="8%"),
        )
    )
