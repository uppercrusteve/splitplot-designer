"""Configuration model and the annotated starter template.

Only one design family is supported: a randomized complete block design with
main plots randomized inside blocks and sub plots randomized inside main plots.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from splitplot_designer.errors import ConfigError

CODE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,11}$")
TREATMENT_UNITS = ("plot_mean", "replicates")


@dataclass(frozen=True)
class Level:
    """One treatment level. ``code`` is ASCII and used in files and maps."""

    code: str
    label: str


@dataclass(frozen=True)
class Layout:
    """Plot geometry in metres and vine counts."""

    plot_length_m: float
    plot_width_m: float
    rows_per_plot: int
    vines_per_row: int
    buffer_rows: int
    row_spacing_m: float
    vine_spacing_m: float

    @property
    def plot_area_m2(self) -> float:
        return self.plot_length_m * self.plot_width_m

    @property
    def vines_per_plot(self) -> int:
        return self.rows_per_plot * self.vines_per_row

    @property
    def expected_length_m(self) -> float:
        return self.vines_per_row * self.vine_spacing_m

    @property
    def expected_width_m(self) -> float:
        return self.rows_per_plot * self.row_spacing_m


@dataclass(frozen=True)
class Sampling:
    """How many sampling points a plot carries and how they are treated."""

    points_per_plot: int = 1
    treated_as: str = "plot_mean"

    @property
    def is_pseudo_replication_risk(self) -> bool:
        return self.points_per_plot > 1 and self.treated_as == "replicates"


@dataclass(frozen=True)
class DesignConfig:
    """Fully resolved, immutable experiment configuration."""

    title: str
    blocks: int
    main_plot_name: str
    main_levels: tuple[Level, ...]
    sub_plot_name: str
    sub_levels: tuple[Level, ...]
    layout: Layout
    seed: int
    sampling: Sampling = Sampling()

    @property
    def plots_per_block(self) -> int:
        return len(self.main_levels) * len(self.sub_levels)

    @property
    def total_plots(self) -> int:
        return self.blocks * self.plots_per_block


def _line(lines: dict[str, int], path: str, fallback: int) -> int:
    return lines.get(path, fallback)


def _fail(message: str, path: str, lines: dict[str, int], fallback: int) -> ConfigError:
    return ConfigError(message, line=_line(lines, path, fallback))


def _require_mapping(
    data: dict[str, Any], key: str, path: str, lines: dict[str, int], fallback: int
) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise _fail(f"缺少映射节 `{key}` (missing mapping `{key}`)", path, lines, fallback)
    return value


def _require_str(
    data: dict[str, Any], key: str, path: str, lines: dict[str, int], fallback: int
) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"`{key}` 必须是非空字符串 (must be a non-empty string)", path, lines, fallback)
    return value.strip()


def _require_int(
    data: dict[str, Any], key: str, path: str, lines: dict[str, int], fallback: int
) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(f"`{key}` 必须是整数 (must be an integer)", path, lines, fallback)
    return value


def _require_float(
    data: dict[str, Any], key: str, path: str, lines: dict[str, int], fallback: int
) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _fail(f"`{key}` 必须是数字 (must be a number)", path, lines, fallback)
    return float(value)


def build_config(data: dict[str, Any], lines: dict[str, int], path=None) -> DesignConfig:
    """Convert a validated raw document into :class:`DesignConfig`."""

    experiment = _require_mapping(data, "experiment", "experiment", lines, 1)

    title = _require_str(experiment, "title", "experiment.title", lines, 1)
    blocks = _require_int(experiment, "blocks", "experiment.blocks", lines, 1)
    seed = _require_int(experiment, "seed", "experiment.seed", lines, 1)

    main = _require_mapping(experiment, "main_plot", "experiment.main_plot", lines, 1)
    sub = _require_mapping(experiment, "sub_plot", "experiment.sub_plot", lines, 1)
    layout_data = _require_mapping(experiment, "layout", "experiment.layout", lines, 1)

    def levels_for(
        section: dict[str, Any], section_path: str, fallback: int
    ) -> tuple[Level, ...]:
        raw_levels = section.get("levels")
        if not isinstance(raw_levels, list):
            raise _fail(
                f"`{section_path}.levels` 必须是列表 (must be a list)",
                f"{section_path}.levels",
                lines,
                fallback,
            )
        out: list[Level] = []
        for index, item in enumerate(raw_levels):
            item_path = f"{section_path}.levels[{index}]"
            if not isinstance(item, dict):
                raise _fail(
                    f"水平 {index + 1} 必须是映射 (level must be a mapping)",
                    item_path,
                    lines,
                    fallback,
                )
            out.append(
                Level(
                    code=_require_str(item, "code", f"{item_path}.code", lines, fallback),
                    label=_require_str(item, "label", f"{item_path}.label", lines, fallback),
                )
            )
        return tuple(out)

    main_levels = levels_for(main, "experiment.main_plot", 1)
    sub_levels = levels_for(sub, "experiment.sub_plot", 1)

    layout = Layout(
        plot_length_m=_require_float(
            layout_data, "plot_length_m", "experiment.layout.plot_length_m", lines, 1
        ),
        plot_width_m=_require_float(
            layout_data, "plot_width_m", "experiment.layout.plot_width_m", lines, 1
        ),
        rows_per_plot=_require_int(
            layout_data, "rows_per_plot", "experiment.layout.rows_per_plot", lines, 1
        ),
        vines_per_row=_require_int(
            layout_data, "vines_per_row", "experiment.layout.vines_per_row", lines, 1
        ),
        buffer_rows=_require_int(
            layout_data, "buffer_rows", "experiment.layout.buffer_rows", lines, 1
        ),
        row_spacing_m=_require_float(
            layout_data, "row_spacing_m", "experiment.layout.row_spacing_m", lines, 1
        ),
        vine_spacing_m=_require_float(
            layout_data, "vine_spacing_m", "experiment.layout.vine_spacing_m", lines, 1
        ),
    )

    sampling = Sampling()
    sampling_data = experiment.get("sampling")
    if isinstance(sampling_data, dict):
        points = sampling_data.get("points_per_plot", 1)
        treated = sampling_data.get("treated_as", "plot_mean")
        if isinstance(points, int) and not isinstance(points, bool):
            sampling = Sampling(points_per_plot=points, treated_as=str(treated))

    return DesignConfig(
        title=title,
        blocks=blocks,
        main_plot_name=_require_str(main, "name", "experiment.main_plot.name", lines, 1),
        main_levels=main_levels,
        sub_plot_name=_require_str(sub, "name", "experiment.sub_plot.name", lines, 1),
        sub_levels=sub_levels,
        layout=layout,
        seed=seed,
        sampling=sampling,
    )


TEMPLATE = """\
# splitplot-designer 配置 / configuration
# 合成演示（非实测数据） / synthetic demo (not observed data)
experiment:
  title: 香格里拉葡萄园行间生草与叶幕管理裂区试验
  # 完整区组数，必须 >= 3 (blocks, >= 3)
  blocks: 4
  main_plot:
    # 主区因子：行间管理 (main-plot factor)
    name: floor_management
    levels:
      - {code: CK, label: 清耕}
      - {code: NG, label: 自然生草}
  sub_plot:
    # 副区因子：叶幕高度 (sub-plot factor)
    name: canopy_height
    levels:
      - {code: C, label: 常规叶幕}
      - {code: H12, label: 叶幕 1.2 m}
      - {code: H14, label: 叶幕 1.4 m}
  layout:
    # 小区长（沿行向，m）应 ≈ vines_per_row × vine_spacing_m
    plot_length_m: 20
    # 小区宽（跨行向，m）应 ≈ rows_per_plot × row_spacing_m
    plot_width_m: 8
    rows_per_plot: 4
    vines_per_row: 20
    # 小区间与区组间的缓冲行，必须 >= 1 (buffer rows, >= 1)
    buffer_rows: 1
    row_spacing_m: 2.0
    vine_spacing_m: 1.0
  # 每小区采样点数量；> 1 时统计单元仍是小区，不是采样点
  sampling:
    points_per_plot: 3
    # plot_mean = 先求小区均值（推荐）；replicates = 把采样点当重复（伪重复风险）
    treated_as: plot_mean
  # 随机化种子，必须为 0..4294967295 的整数
  seed: 20251117
"""


def template_text() -> str:
    """Return the commented starter configuration."""

    return TEMPLATE
