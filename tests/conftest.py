"""Shared fixtures and synthetic configurations for the test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from splitplot_designer.config import DesignConfig, Layout, Level, Sampling


def make_config(**overrides: object) -> DesignConfig:
    values: dict[str, object] = {
        "title": "合成裂区试验 / synthetic split-plot",
        "blocks": 4,
        "main_plot_name": "floor",
        "main_levels": (Level("CK", "清耕"), Level("NG", "自然生草")),
        "sub_plot_name": "canopy",
        "sub_levels": (Level("C", "常规"), Level("H12", "1.2 m"), Level("H14", "1.4 m")),
        "layout": Layout(
            plot_length_m=20,
            plot_width_m=8,
            rows_per_plot=4,
            vines_per_row=20,
            buffer_rows=1,
            row_spacing_m=2.0,
            vine_spacing_m=1.0,
        ),
        "seed": 20251117,
        "sampling": Sampling(),
    }
    values.update(overrides)
    return DesignConfig(**values)  # type: ignore[arg-type]


BASE_YAML = """\
experiment:
  title: 合成验证配置
  blocks: {blocks}
  main_plot:
    name: floor
    levels:
      - {{code: CK, label: 清耕}}
      - {{code: NG, label: 自然生草}}
  sub_plot:
    name: canopy
    levels:
      - {{code: C, label: 常规}}
      - {{code: H12, label: 叶幕 1.2 m}}
  layout:
    plot_length_m: {length}
    plot_width_m: 8
    rows_per_plot: 4
    vines_per_row: 20
    buffer_rows: {buffer}
    row_spacing_m: 2.0
    vine_spacing_m: 1.0
  sampling:
    points_per_plot: 1
    treated_as: plot_mean
  seed: {seed}
"""


@pytest.fixture
def config() -> DesignConfig:
    return make_config()


@pytest.fixture
def yaml_file(tmp_path: Path):
    """Write a YAML document built from BASE_YAML with overrides."""

    def write(**overrides: object) -> Path:
        values = {"blocks": 4, "length": 20, "buffer": 1, "seed": 20251117}
        values.update(overrides)
        path = tmp_path / "design.yaml"
        path.write_text(BASE_YAML.format(**values), encoding="utf-8")
        return path

    return write
