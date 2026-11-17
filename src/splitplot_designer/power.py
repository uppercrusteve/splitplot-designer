"""Monte Carlo power for the main-plot, sub-plot and interaction tests.

The data-generating process is the split-plot linear model

    y = grand + block + main + sub + main*sub + e_main + e_sub

with ``e_main`` drawn once per block x main cell and ``e_sub`` drawn per plot.
The intraclass correlation ``icc`` is the share of total error variance that
lives at the whole-plot level, so a larger ICC makes main-plot contrasts harder
to detect. ``effect`` is Cohen's f against the total error SD of 1. Tests use
the correct error strata; the residual variance is never used as the
denominator for a main effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
from scipy import stats

DEFAULT_SEED = 20251117
MAX_BLOCKS = 12
POWER_TARGET = 0.80


@dataclass(frozen=True)
class PowerResult:
    blocks: int
    effect: float
    icc: float
    alpha: float
    sims: int
    seed: int
    main_levels: int
    sub_levels: int
    error_df: int
    power_main: float
    power_sub: float
    power_interaction: float
    recommended_blocks: int | None

    def as_dict(self) -> dict[str, object]:
        return {
            "method": "Monte Carlo split-plot simulation, correct error strata",
            "assumptions": {
                "model": "y = grand + block + main + sub + main*sub + e_main + e_sub",
                "effect_size": "Cohen's f relative to total error SD = 1",
                "icc": "e_main variance / total error variance",
                "test_main": "MS_main / MS_block:main",
                "test_sub": "MS_sub / MS_residual",
                "test_interaction": "MS_main:sub / MS_residual",
                "alpha": self.alpha,
                "two_sided": True,
            },
            "inputs": {
                "blocks": self.blocks,
                "effect": self.effect,
                "icc": self.icc,
                "alpha": self.alpha,
                "sims": self.sims,
                "seed": self.seed,
                "main_levels": self.main_levels,
                "sub_levels": self.sub_levels,
            },
            "error_df": self.error_df,
            "power": {
                "main": self.power_main,
                "sub": self.power_sub,
                "interaction": self.power_interaction,
            },
            "recommended_blocks_for_80pct_main": self.recommended_blocks,
            "note": "Simulated power for a synthetic balanced design; not observed data.",
        }


def _effect_vector(levels: int, cohens_f: float) -> np.ndarray:
    """Evenly spaced effects scaled so that ``cohens_f`` is the actual f.

    Cohen's f is ``sqrt(sum(effect^2) / (levels * sigma^2))``; with the total
    error SD fixed at 1 the vector norm is therefore ``f * sqrt(levels)``.
    """

    base = np.linspace(-1.0, 1.0, levels, dtype=float)
    base -= base.mean()
    norm = np.linalg.norm(base)
    if norm == 0:
        return base
    return base / norm * cohens_f * np.sqrt(levels)


def _dummies(values: np.ndarray, levels: int) -> np.ndarray:
    matrix = np.zeros((values.size, levels - 1), dtype=float)
    for column in range(levels - 1):
        matrix[:, column] = (values == column + 1).astype(float)
    return matrix


def _design(
    block: np.ndarray,
    main: np.ndarray,
    sub: np.ndarray,
    blocks: int,
    main_levels: int,
    sub_levels: int,
) -> tuple[np.ndarray, dict[str, slice]]:
    block_d = _dummies(block, blocks)
    main_d = _dummies(main, main_levels)
    sub_d = _dummies(sub, sub_levels)
    interaction = np.column_stack(
        [main_d[:, i] * sub_d[:, j]
         for i in range(main_levels - 1)
         for j in range(sub_levels - 1)]
    )
    block_main = np.column_stack(
        [block_d[:, i] * main_d[:, j]
         for i in range(blocks - 1)
         for j in range(main_levels - 1)]
    )
    matrix = np.column_stack(
        [np.ones((block.size, 1)), block_d, main_d, block_main, sub_d, interaction]
    )

    def span(start: int, width: int) -> slice:
        return slice(start, start + width)

    cursor = 1
    cursor += blocks - 1
    main_slice = span(cursor, main_levels - 1)
    cursor += main_levels - 1
    block_main_slice = span(cursor, (blocks - 1) * (main_levels - 1))
    cursor += (blocks - 1) * (main_levels - 1)
    sub_slice = span(cursor, sub_levels - 1)
    cursor += sub_levels - 1
    inter_slice = span(cursor, (main_levels - 1) * (sub_levels - 1))
    return matrix, {
        "main": main_slice,
        "block_main": block_main_slice,
        "sub": sub_slice,
        "interaction": inter_slice,
    }


def _rss(matrix: np.ndarray, y: np.ndarray) -> float:
    coefficients, _, rank, _ = np.linalg.lstsq(matrix, y, rcond=None)
    del rank
    residual = y - matrix @ coefficients
    return float(residual @ residual)


def _one_simulation(
    rng: np.random.Generator,
    blocks: int,
    main_levels: int,
    sub_levels: int,
    main_effects: np.ndarray,
    sub_effects: np.ndarray,
    interaction_effects: np.ndarray,
    block_effects: np.ndarray,
    icc: float,
    alpha: float,
) -> tuple[bool, bool, bool]:
    block, main, sub = np.meshgrid(
        np.arange(1, blocks + 1),
        np.arange(1, main_levels + 1),
        np.arange(1, sub_levels + 1),
        indexing="ij",
    )
    block = block.ravel()
    main = main.ravel()
    sub = sub.ravel()

    design, sl = _design(block, main, sub, blocks, main_levels, sub_levels)
    block_main = (block - 1) * main_levels + (main - 1)
    e_main = rng.normal(0.0, np.sqrt(icc), blocks * main_levels)
    e_sub = rng.normal(0.0, np.sqrt(1.0 - icc), block.size)

    y = (
        100.0
        + block_effects[block - 1]
        + main_effects[main - 1]
        + sub_effects[sub - 1]
        + interaction_effects[main - 1, sub - 1]
        + e_main[block_main]
        + e_sub
    )

    rss_full = _rss(design, y)
    rss_sub = _rss(np.delete(design, sl["sub"], axis=1), y)
    rss_inter = _rss(np.delete(design, sl["interaction"], axis=1), y)

    df_main = main_levels - 1
    df_block_main = (blocks - 1) * (main_levels - 1)
    df_sub = sub_levels - 1
    df_inter = (main_levels - 1) * (sub_levels - 1)
    df_error = block.size - (blocks * main_levels + df_sub + df_inter)

    # Main effects live in the whole-plot stratum. Deleting main from a model
    # that already contains block x main only tests the contrast at the
    # reference block (the cell means are already saturated). Compute the
    # classical extra sum of squares on the block x main cell-means models
    # instead: block -> block + main -> block + main + block:main.
    block_cols = np.r_[0:1, 1:blocks]
    main_cols = np.r_[block_cols, np.arange(sl["main"].start, sl["main"].stop)]
    cell_cols = np.r_[main_cols, np.arange(sl["block_main"].start, sl["block_main"].stop)]
    rss_block = _rss(design[:, block_cols], y)
    rss_block_main = _rss(design[:, main_cols], y)
    rss_cell = _rss(design[:, cell_cols], y)

    ss_main = max(rss_block - rss_block_main, 0.0)
    ss_block_main = max(rss_block_main - rss_cell, 1e-12)
    ms_error = max(rss_full, 1e-12) / max(df_error, 1)

    f_main = (ss_main / df_main) / (ss_block_main / df_block_main)
    f_sub = (max(rss_sub - rss_full, 0.0) / df_sub) / ms_error
    f_inter = (max(rss_inter - rss_full, 0.0) / df_inter) / ms_error

    p_main = float(stats.f.sf(f_main, df_main, df_block_main))
    p_sub = float(stats.f.sf(f_sub, df_sub, df_error))
    p_inter = float(stats.f.sf(f_inter, df_inter, df_error))
    return p_main < alpha, p_sub < alpha, p_inter < alpha


def _run(
    blocks: int,
    effect: float,
    icc: float,
    alpha: float,
    main_levels: int,
    sub_levels: int,
    sims: int,
    seed: int,
) -> tuple[float, float, float, int]:
    rng = np.random.default_rng(seed)
    main_effects = _effect_vector(main_levels, effect)
    sub_effects = _effect_vector(sub_levels, effect)
    interaction = np.outer(main_effects, sub_effects)
    scale = np.linalg.norm(interaction)
    if scale > 0:
        interaction = interaction / scale * effect * np.sqrt(main_levels * sub_levels)
    block_effects = _effect_vector(blocks, 0.35)

    hits_main = 0
    hits_sub = 0
    hits_inter = 0
    for _ in range(sims):
        main_hit, sub_hit, inter_hit = _one_simulation(
            rng, blocks, main_levels, sub_levels, main_effects, sub_effects,
            interaction, block_effects, icc, alpha,
        )
        hits_main += int(main_hit)
        hits_sub += int(sub_hit)
        hits_inter += int(inter_hit)
    df_error = blocks * main_levels * sub_levels - (
        blocks * main_levels + sub_levels - 1 + (main_levels - 1) * (sub_levels - 1)
    )
    return hits_main / sims, hits_sub / sims, hits_inter / sims, df_error


def simulate_power(
    *,
    blocks: int,
    effect: float,
    icc: float,
    alpha: float = 0.05,
    main_levels: int = 2,
    sub_levels: int = 3,
    sims: int = 500,
    seed: int = DEFAULT_SEED,
    recommend: bool = True,
) -> PowerResult:
    """Run the simulation and optionally search for an adequate block count."""

    if blocks < 2:
        raise ValueError("blocks 必须 >= 2 (blocks must be >= 2)")
    if blocks > 20:
        raise ValueError("blocks 必须 <= 20 (blocks must be <= 20)")
    if not 0.0 <= effect <= 3.0:
        raise ValueError("effect 必须在 0..3 之间 (effect must be within 0..3)")
    if not 0.0 <= icc < 1.0:
        raise ValueError("icc 必须在 0..1 之间（不含 1）(icc must be in [0, 1))")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha 必须在 0..1 之间 (alpha must be within (0, 1))")
    if main_levels < 2 or sub_levels < 2:
        raise ValueError("主区与副区水平数都必须 >= 2 (both factors need >= 2 levels)")
    if sims < 10:
        raise ValueError("sims 必须 >= 10 (sims must be >= 10)")
    if not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed 越界 (seed out of range)")

    power_main, power_sub, power_inter, df_error = _run(
        blocks, effect, icc, alpha, main_levels, sub_levels, sims, seed
    )

    recommended: int | None = None
    if recommend and power_main < POWER_TARGET and blocks < MAX_BLOCKS:
        for candidate in range(blocks + 1, min(MAX_BLOCKS, blocks + 6) + 1):
            candidate_power, _, _, _ = _run(
                candidate, effect, icc, alpha, main_levels, sub_levels,
                min(sims, 300), seed,
            )
            if candidate_power >= POWER_TARGET:
                recommended = candidate
                break

    return PowerResult(
        blocks=blocks,
        effect=effect,
        icc=icc,
        alpha=alpha,
        sims=sims,
        seed=seed,
        main_levels=main_levels,
        sub_levels=sub_levels,
        error_df=df_error,
        power_main=power_main,
        power_sub=power_sub,
        power_interaction=power_inter,
        recommended_blocks=recommended,
    )


def normal_approximation(blocks: int, effect: float, icc: float, alpha: float = 0.05,
                         main_levels: int = 2) -> float:
    """Analytic rough check for the main-effect power (never for reporting alone)."""

    n_main_units = blocks * main_levels
    se = np.sqrt(2.0 * icc / n_main_units) / max(effect, 1e-9)
    z = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    if se == 0:
        return 1.0
    return float(1.0 - NormalDist().cdf(z - 1.0 / se))


def format_report(result: PowerResult) -> str:
    """Bilingual human-readable report with assumptions and a data disclaimer."""

    def pct(value: float) -> str:
        return f"{value * 100:5.1f}%"

    lines = [
        "裂区试验功效模拟 / split-plot power simulation  [合成计算，非实测]",
        "=" * 68,
        f"区组 blocks           : {result.blocks}",
        f"主区水平 main levels  : {result.main_levels}",
        f"副区水平 sub levels   : {result.sub_levels}",
        f"效应量 effect (Cohen's f, 误差 SD = 1) : {result.effect:g}",
        f"ICC (主区误差方差占比)                : {result.icc:g}",
        f"alpha                 : {result.alpha:g} (双侧 / two-sided)",
        f"模拟次数 sims         : {result.sims}  (seed {result.seed})",
        f"残差 df error df      : {result.error_df}",
        "",
        "模拟功效 / simulated power",
        f"  主效应 main         : {pct(result.power_main)}",
        f"  副效应 sub          : {pct(result.power_sub)}",
        f"  交互作用 interaction: {pct(result.power_interaction)}",
        "",
    ]
    if result.power_main >= POWER_TARGET:
        lines.append("主效应功效已达 80% / main-effect power already reaches 80%.")
    elif result.recommended_blocks is not None:
        lines.append(
            f"建议区组数 / suggested blocks: {result.recommended_blocks} "
            f"(使主效应功效 >= 80%)"
        )
    else:
        lines.append(
            "在 12 个区组以内仍未达 80%；考虑增大效应量、降低 ICC 或增加主区水平。"
            " / Still below 80% at 12 blocks; increase effect, reduce ICC, or add main levels."
        )

    lines.extend([
        "",
        "模型 / model",
        "  y = grand + block + main + sub + main*sub + e_main + e_sub",
        "  主效应检验 / main test            : MS_main / MS_block:main",
        "  副效应检验 / sub test             : MS_sub / MS_residual",
        "  交互检验 / interaction test       : MS_main:sub / MS_residual",
        "",
        "假设 / assumptions",
        "  - 完整区组、平衡设计，无缺失小区；区组为随机效应，处理为固定效应。",
        "  - 误差正态独立；ICC 固定且已知；方差齐性。",
        "  - 效应量按总误差 SD = 1 标准化，与田间变异尺度无关。",
        "  - 功效是模拟频率，不是对某次试验的事后保证（Casler 2015; Gomez & Gomez 1984）。",
        "  - 主区水平默认 2、副区水平默认 3；其他结构请用 --main-levels / --sub-levels。",
        "  - 合成演示，不读取任何观测数据。",
    ])
    return "\n".join(lines)
