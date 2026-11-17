"""Draft a methods paragraph straight from a validated design.

The generated text is deliberately plain so it can be pasted into a protocol or
manuscript and edited. Counts, dimensions, buffer and the statistical unit are
all derived from the configuration rather than typed by hand.
"""

from __future__ import annotations

from splitplot_designer.config import DesignConfig


def _level_text(levels) -> str:
    return "、".join(f"{level.label}（{level.code}）" for level in levels)


def build_methods_text(config: DesignConfig) -> str:
    layout = config.layout
    sampling = config.sampling
    if sampling.points_per_plot == 1:
        sampling_text = (
            "每小区设 1 个采样点，采样点覆盖小区中部连续植株。"
        )
    elif sampling.treated_as == "plot_mean":
        sampling_text = (
            f"每小区设 {sampling.points_per_plot} 个采样点，分析前先按小区求算术均值，"
            "采样点本身不作为重复。"
        )
    else:
        sampling_text = (
            f"每小区设 {sampling.points_per_plot} 个采样点，分析时把采样点视作重复，"
            "并在讨论中说明伪重复风险。"
        )

    return f"""\
【试验设计（可直接修改后用于论文/方案）】

本试验在［地点］的［园块］进行，采用随机完全区组裂区设计，共设 {config.blocks} 个区组。\
主区因子为{config.main_plot_name}，设 {_level_text(config.main_levels)} 共 \
{len(config.main_levels)} 个水平；副区因子为{config.sub_plot_name}，设 \
{_level_text(config.sub_levels)} 共 {len(config.sub_levels)} 个水平。每个区组内主区独立随机排列，\
每个主区内副区独立随机排列，{config.blocks} 个区组均包含全部 \
{config.total_plots // config.blocks} 个主区×副区组合，无缺失小区。随机化由 \
splitplot-designer 0.1.0 以随机种子 {config.seed} 生成，可完整复现。

每小区长 {layout.plot_length_m:g} m（沿行向）、宽 {layout.plot_width_m:g} m（跨行向），\
面积 {layout.plot_area_m2:g} m²，种植 {layout.rows_per_plot} 行 × \
{layout.vines_per_row} 株 = {layout.vines_per_plot} 株，行距 {layout.row_spacing_m:g} m、\
株距 {layout.vine_spacing_m:g} m。相邻区组之间保留 {layout.buffer_rows} 行 \
{layout.vines_per_row} 株 = {layout.vines_per_plot} 株，行距 {layout.row_spacing_m:g} m、\
株距 {layout.vine_spacing_m:g} m。相邻区组之间保留 {layout.buffer_rows} 行 \
（{layout.buffer_rows * layout.row_spacing_m:g} m）缓冲行；同一区组内的小区沿行向相邻、\
不留行间空隙。{config.title}，各处理按统一农事日历管理，除试验因子外其余措施一致。

统计单元为小区（plot），不是单株或单个采样点。{sampling_text}统计分析采用裂区线性模型，\
主区效应以区组×主区（block×main）为误差项，副区效应及主区×副区交互以小区残差为误差项；\
主区效应不在完全随机模型下检验。分析前检查残差正态性与方差齐性，必要时对响应变量作变换；\
多重比较采用［Tukey HSD / 计划对比］，并报告效应量与置信区间。响应变量为［指标名称与单位］。

【English version】

The trial was laid out as a randomized complete block split-plot design with \
{config.blocks} blocks at [site] in [season]. The whole-plot factor \
{config.main_plot_name} had {len(config.main_levels)} levels ({_level_text(config.main_levels)}); \
the sub-plot factor {config.sub_plot_name} had {len(config.sub_levels)} levels \
({_level_text(config.sub_levels)}). Whole plots were randomized independently within each block, \
and sub plots independently within each whole plot. All {config.total_plots // config.blocks} \
treatment combinations were present in every block, with no missing plot. Randomization was \
generated with splitplot-designer 0.1.0 using seed {config.seed} and is fully reproducible.

Each plot measured {layout.plot_length_m:g} m along the row direction by \
{layout.plot_width_m:g} m across rows ({layout.plot_area_m2:g} m²), containing \
{layout.rows_per_plot} rows × {layout.vines_per_row} vines at \
{layout.row_spacing_m:g} m row spacing and {layout.vine_spacing_m:g} m vine spacing. \
{layout.buffer_rows} buffer row(s) ({layout.buffer_rows * layout.row_spacing_m:g} m) separated \
adjacent blocks; plots within a block sat side by side along the row direction without extra \
gaps. The experimental unit was the whole plot, never an individual vine or sampling point. \
Data were analysed with a split-plot model: whole-plot effects were tested against the \
block × main mean square, and sub-plot and interaction effects against the plot residual. \
Residual diagnostics and [Tukey HSD / planned contrasts] followed the fit.

【需人工替换】地点、年份、品种、响应变量与单位、多重比较方法、田间管理细节。
"""


def build_methods_facts(config: DesignConfig) -> dict[str, object]:
    """Key facts backing the paragraph, useful for audits."""

    return {
        "blocks": config.blocks,
        "main_levels": len(config.main_levels),
        "sub_levels": len(config.sub_levels),
        "plots": config.total_plots,
        "plot_length_m": config.layout.plot_length_m,
        "plot_width_m": config.layout.plot_width_m,
        "plot_area_m2": config.layout.plot_area_m2,
        "buffer_rows": config.layout.buffer_rows,
        "statistical_unit": "plot",
        "seed": config.seed,
        "sampling_points_per_plot": config.sampling.points_per_plot,
        "sampling_treated_as": config.sampling.treated_as,
    }
