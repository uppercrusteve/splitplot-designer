"""Field-map rendering (PNG and SVG) from a real allocation."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.colors import to_rgba  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

if TYPE_CHECKING:
    from splitplot_designer.config import DesignConfig, Level
    from splitplot_designer.design import PlotAssignment

FONT_STACK = (
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "DejaVu Sans",
)
INK = "#1F2933"
MUTED = "#5B6770"
BUFFER_COLOR = "#E8E5DF"
FIELD_BORDER = "#2F3A42"
PALETTE = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9")


def _font_family() -> list[str]:
    available = {entry.name for entry in font_manager.fontManager.ttflist}
    chosen = [name for name in FONT_STACK if name in available]
    return chosen or ["DejaVu Sans"]


def _color_map(levels: tuple[Level, ...]) -> dict[str, str]:
    return {level.code: PALETTE[index % len(PALETTE)] for index, level in enumerate(levels)}


def _draw_header(
    header,
    config: DesignConfig,
    levels: tuple[Level, ...],
    colors: dict[str, str],
    seed: int,
    total_rows: int,
) -> None:
    header.set_axis_off()
    header.set_xlim(0, 1)
    header.set_ylim(0, 1)

    header.text(
        0.0,
        0.84,
        config.title,
        fontsize=14,
        fontweight="bold",
        color=INK,
        ha="left",
        va="center",
    )
    subtitle = (
        f"裂区试验 · {config.blocks} 区组 × {len(config.main_levels)} 主区 × "
        f"{len(config.sub_levels)} 副区 = {config.total_plots} 小区  |  "
        f"{config.layout.plot_length_m:g} m × {config.layout.plot_width_m:g} m "
        f"= {config.layout.plot_area_m2:g} m²/小区  |  行距 "
        f"{config.layout.row_spacing_m:g} m"
    )
    header.text(0.0, 0.55, subtitle, fontsize=8.2, color=MUTED, ha="left", va="center")
    header.text(
        0.0,
        0.30,
        f"合成演示数据 · seed = {seed} · 行数 {total_rows} · "
        f"统计单元 = 小区（非单株/采样点）",
        fontsize=7.6,
        color=MUTED,
        ha="left",
        va="center",
    )

    handles = [
        Patch(facecolor=to_rgba(colors[level.code], 0.55),
              edgecolor=colors[level.code], label=f"{level.code}  {level.label}")
        for level in levels
    ]
    handles.append(Patch(facecolor=BUFFER_COLOR, edgecolor="#B9B2A7", label="缓冲行 / buffer"))
    handles.append(Patch(facecolor="none", edgecolor=FIELD_BORDER, linewidth=2.0,
                         label="主区边界 / main plot"))
    header.legend(
        handles=handles,
        loc="lower left",
        bbox_to_anchor=(0.0, 0.0),
        ncol=len(handles),
        frameon=False,
        fontsize=7.6,
        handlelength=1.3,
        handleheight=0.9,
        columnspacing=1.1,
        labelcolor=INK,
    )

    header.annotate(
        "N",
        xy=(0.975, 0.30),
        xytext=(0.975, 0.72),
        xycoords="axes fraction",
        ha="center",
        va="center",
        fontsize=11,
        fontweight="bold",
        color=INK,
        arrowprops={"arrowstyle": "-|>", "color": INK, "linewidth": 1.3},
    )


def _draw_field(
    ax,
    config: DesignConfig,
    assignments: list[PlotAssignment],
    total_rows: int,
    colors: dict[str, str],
) -> None:
    layout = config.layout
    field_length = config.layout.vines_per_row * config.plots_per_block * layout.vine_spacing_m
    field_width = total_rows * layout.row_spacing_m

    ax.set_facecolor("white")
    ax.add_patch(
        Rectangle((0, 0), field_length, field_width, facecolor="#F4F6F5",
                  edgecolor="none", zorder=0)
    )

    main_groups: dict[str, list[PlotAssignment]] = defaultdict(list)
    block_rows: dict[int, tuple[int, int]] = {}
    for assignment in assignments:
        low, high = block_rows.get(assignment.block, (assignment.row_start, assignment.row_end))
        block_rows[assignment.block] = (
            min(low, assignment.row_start),
            max(high, assignment.row_end),
        )
        x0 = (assignment.vine_start - 1) * layout.vine_spacing_m
        y0 = (total_rows - assignment.row_end) * layout.row_spacing_m
        width = layout.vines_per_row * layout.vine_spacing_m
        height = layout.rows_per_plot * layout.row_spacing_m
        color = colors[assignment.sub_code]
        ax.add_patch(
            Rectangle(
                (x0, y0),
                width,
                height,
                facecolor=to_rgba(color, 0.42),
                edgecolor=color,
                linewidth=0.8,
                zorder=2,
            )
        )
        main_key = "-".join(assignment.plot_id.split("-")[:2])
        main_groups[main_key].append(assignment)

        ax.text(
            x0 + width / 2,
            y0 + height * 0.47,
            assignment.sub_code,
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
            color="#12232E",
            zorder=4,
        )
        ax.text(
            x0 + width / 2,
            y0 + height * 0.28,
            next(level.label for level in config.sub_levels
                 if level.code == assignment.sub_code),
            ha="center",
            va="center",
            fontsize=6.2,
            color="#12232E",
            zorder=4,
        )
        ax.text(
            x0 + width / 2,
            y0 + height * 0.11,
            assignment.plot_id,
            ha="center",
            va="center",
            fontsize=5.4,
            color=MUTED,
            zorder=4,
        )

    for key, group in sorted(main_groups.items()):
        xs = [(item.vine_start - 1) * layout.vine_spacing_m for item in group]
        ys = [(total_rows - item.row_end) * layout.row_spacing_m for item in group]
        x0 = min(xs)
        y0 = min(ys)
        width = (max(item.vine_end for item in group) - min(item.vine_start for item in group)
                 + 1) * layout.vine_spacing_m
        height = (max(item.row_end for item in group) - min(item.row_start for item in group)
                  + 1) * layout.row_spacing_m
        ax.add_patch(
            Rectangle((x0, y0), width, height, facecolor="none",
                      edgecolor=FIELD_BORDER, linewidth=2.1, zorder=5)
        )
        code = group[0].main_code
        position = key.split("-")[1]
        label = next(level.label for level in config.main_levels if level.code == code)
        ax.text(
            x0 + 1.0,
            y0 + height - 0.9,
            f"{position}  {label}",
            ha="left",
            va="top",
            fontsize=6.0,
            fontweight="bold",
            color=INK,
            zorder=6,
            bbox={"facecolor": "white", "edgecolor": "#C9D2D8", "linewidth": 0.35,
                  "boxstyle": "round,pad=0.14", "alpha": 0.88},
        )

    strips: list[tuple[int, int]] = sorted(
        (min(item.row_start for item in group), max(item.row_end for item in group))
        for group in main_groups.values()
    )
    gaps = [
        (strips[index][1] + 1, strips[index + 1][0] - 1)
        for index in range(len(strips) - 1)
        if strips[index + 1][0] - strips[index][1] > 1
    ]
    for gap_bottom, gap_top in gaps:
        y0 = (total_rows - gap_top) * layout.row_spacing_m
        height = (gap_top - gap_bottom + 1) * layout.row_spacing_m
        ax.add_patch(
            Rectangle((0, y0), field_length, height, facecolor=BUFFER_COLOR,
                      edgecolor="none", zorder=1, alpha=0.95)
        )
    for block, (bottom, top) in sorted(block_rows.items()):
        y_center = (total_rows - (top + bottom) / 2) * layout.row_spacing_m
        ax.text(
            -3.0,
            y_center,
            f"区组 {block}\nBlock {block}",
            ha="right",
            va="center",
            fontsize=8.4,
            color=INK,
            linespacing=1.3,
        )

    ax.add_patch(
        Rectangle((0, 0), field_length, field_width, facecolor="none",
                  edgecolor=FIELD_BORDER, linewidth=2.4, zorder=5)
    )

    ax.set_xlim(-18, field_length + 3)
    ax.set_ylim(-6.5, field_width + 4)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("沿行向距离 / distance along rows (m)", fontsize=8.2)
    ax.set_ylabel("跨行向距离 / across rows (m)", fontsize=8.2)
    ax.tick_params(labelsize=6.8, colors=MUTED, length=2.5)
    ax.set_xticks(range(0, int(field_length) + 1, 20))
    ax.set_yticks(range(0, int(field_width) + 1, 20))
    ax.grid(color="#9AA6AE", linewidth=0.35, alpha=0.28, zorder=0)
    for spine in ax.spines.values():
        spine.set_color("#AEB8BE")
        spine.set_linewidth(0.7)

    scale = 20.0
    ax.plot([0, scale], [-2.2, -2.2], color=INK, linewidth=2.2, solid_capstyle="butt",
            clip_on=False)
    ax.plot([0, 0], [-3.0, -1.4], color=INK, linewidth=1.0, clip_on=False)
    ax.plot([scale, scale], [-3.0, -1.4], color=INK, linewidth=1.0, clip_on=False)
    ax.text(scale / 2, -4.4, f"{scale:g} m", ha="center", va="center",
            fontsize=7.2, color=INK)


def render_field_map(
    config: DesignConfig,
    assignments: list[PlotAssignment],
    total_rows: int,
    output_dir: Path,
    formats: tuple[str, ...] = ("png", "svg"),
    *,
    seed: int | None = None,
) -> list[Path]:
    """Render the layout to the requested formats and return written paths."""

    chosen_seed = config.seed if seed is None else seed
    widths = {"png": 150, "svg": 150}
    levels = config.sub_levels
    layout = config.layout
    colors = _color_map(levels)
    height = min(12.0, max(5.4, total_rows * 0.1 + 3.6))
    field_length = (
        layout.vines_per_row * config.plots_per_block * layout.vine_spacing_m
    )

    with plt.rc_context({
        "font.family": "sans-serif",
        "font.sans-serif": _font_family(),
        "axes.unicode_minus": False,
        "text.color": INK,
        "svg.fonttype": "none",
    }):
        fig = plt.figure(figsize=(14.0, height), facecolor="white")
        header = fig.add_axes([0.12, 0.77, 0.78, 0.19])
        map_ax = fig.add_axes([0.155, 0.07, 0.72, 0.62])
        _draw_header(header, config, levels, colors, chosen_seed, total_rows)
        _draw_field(map_ax, config, assignments, total_rows, colors)
        fig.text(
            0.155,
            0.018,
            f"总尺寸 {field_length:g} m"
            f" × {total_rows * config.layout.row_spacing_m:g} m · "
            f"每小区 {config.layout.rows_per_plot} 行 × {config.layout.vines_per_row} 株 "
            f"= {config.layout.vines_per_plot} 株 · 缓冲行 {config.layout.buffer_rows} 行 × "
            f"{config.layout.row_spacing_m:g} m = "
            f"{config.layout.buffer_rows * config.layout.row_spacing_m:g} m · 合成演示，非实测",
            fontsize=7.0,
            color=MUTED,
        )

        written: list[Path] = []
        for fmt in formats:
            target = output_dir / f"field-map.{fmt}"
            fig.savefig(target, dpi=widths.get(fmt, 150), facecolor="white",
                        bbox_inches="tight", pad_inches=0.18, format=fmt)
            written.append(target)
        plt.close(fig)
    return written
