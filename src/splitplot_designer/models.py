"""Model formulas and error-strata guidance for a split-plot analysis."""

from __future__ import annotations

from splitplot_designer.config import DesignConfig


def _codes(config: DesignConfig, levels) -> str:
    return ", ".join(f"{level.code}={level.label}" for level in levels)


def build_model_text(config: DesignConfig) -> str:
    """Return formulas for statsmodels and R plus the stratification rationale."""

    main = config.main_plot_name
    sub = config.sub_plot_name
    main_df = len(config.main_levels) - 1
    block_df = (config.blocks - 1) * main_df
    # Standard split-plot residual df: a * (r - 1) * (s - 1).
    residual_df = len(config.main_levels) * (
        (config.blocks - 1) * (len(config.sub_levels) - 1)
    )
    sub_df = len(config.sub_levels) - 1
    interaction_df = main_df * sub_df

    return f"""\
裂区模型 / split-plot model  [设计结构：{config.blocks} 区组 × \
{len(config.main_levels)} 主区 × {len(config.sub_levels)} 副区]
主区 / main : {main} ({_codes(config, config.main_levels)})
副区 / sub  : {sub} ({_codes(config, config.sub_levels)})
统计单元 / experimental unit: 小区 plot_id（不是单株、也不是采样点）

误差分层 / error strata  —— 裂区必须这样分
  主区误差 / whole-plot error : block:{main}（block × main），df = {block_df}
  副区误差 / sub-plot error   : 残差 residual，df = {residual_df}
  主区效应用 MS({main}) / MS(block:{main}) 检验；
  副区与交互用各自的 MS / MS(残差) 检验。

statsmodels（含正确的分层检验）
  full = ols("y ~ C(block) + C({main}) + C(block):C({main}) "
             "+ C({sub}) + C({main}):C({sub})", data=plot_means).fit()
  # 不要用 anova_lm 的默认残差检验主区效应；主区 F 的分母取 block:main 的 MS。
  # 等价的混合模型（区组与 block:main 为随机）：
  smf.mixedlm("y ~ C({main}) * C({sub})", plot_means, groups="block",
              re_formula="1",
              vc_formula={{"block_main": "0 + C(block):C({main})"}}).fit()

R
  aov(y ~ {main} * {sub} + Error(block/{main}), data = plot_means)
  lmer(y ~ {main} * {sub} + (1 | block) + (1 | block:{main}),
       data = plot_means)

常见错误 / common mistakes
  1. y ~ {main} * {sub} 的完全随机模型（无区组、无 Error 层）：主区被伪重复，
     主区效应的 df 和误差方差都会算小，p 值偏乐观。
  2. 只加 (1 | block) 而不加 (1 | block:{main})：主区处理仍然
     没有自己的随机截距，等于把主区当固定整块。
  3. 把同一小区的多个采样点当 n 扩大：应先用 plot_id 求均值，或加 (1 | plot_id)，
     并保持主区误差 df = ({config.blocks}-1)×({len(config.main_levels)}-1) = {block_df}。
  4. 用单株数据直接拟合：单株是技术重复，不是独立试验单元。

模型式 / model
  y = grand + block + {main} + {sub} + {main}*{sub} + e_whole + e_plot
  e_whole ~ N(0, sigma_whole^2) 只随 block×{main} 变化；e_plot ~ N(0, sigma_plot^2)。
  交互 df = {interaction_df}；副区 df = {sub_df}；主区 df = {main_df}。
"""


def build_model_summary(config: DesignConfig) -> dict[str, object]:
    """Machine-readable companion to :func:`build_model_text`."""

    return {
        "statistical_unit": "plot",
        "whole_plot_error": f"{config.blocks}:{config.main_plot_name}",
        "sub_plot_error": "residual",
        "main_df": len(config.main_levels) - 1,
        "block_main_df": (config.blocks - 1) * (len(config.main_levels) - 1),
        "sub_df": len(config.sub_levels) - 1,
        "interaction_df": (len(config.main_levels) - 1) * (len(config.sub_levels) - 1),
        "residual_df": len(config.main_levels) * (
            (config.blocks - 1) * (len(config.sub_levels) - 1)
        ),
        "statsmodels_formula": (
            f"y ~ C({config.blocks}) + C({config.main_plot_name}) + "
            f"C({config.blocks}):C({config.main_plot_name}) + C({config.sub_plot_name}) + "
            f"C({config.main_plot_name}):C({config.sub_plot_name})"
        ),
        "r_formula": (
            f"y ~ {config.main_plot_name} * {config.sub_plot_name} + "
            f"Error({config.blocks}/{config.main_plot_name})"
        ),
        "r_lmer_formula": (
            f"y ~ {config.main_plot_name} * {config.sub_plot_name} + "
            f"(1 | {config.blocks}) + (1 | {config.blocks}:{config.main_plot_name})"
        ),
        "warnings": [
            "A completely randomized model for these data is wrong: main plots are "
            "whole-plot units and need the block:main error stratum.",
            "Do not treat vines or sampling points inside a plot as replicates.",
        ],
    }
