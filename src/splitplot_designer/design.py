"""Randomized split-plot allocation and machine-readable design exports."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from splitplot_designer.config import DesignConfig, Level
from splitplot_designer.errors import OutputError
from splitplot_designer.render import render_field_map

SCHEMA_VERSION = "1.0"
CSV_HEADER = (
    "block",
    "main_code",
    "sub_code",
    "plot_id",
    "row_start",
    "row_end",
    "vine_start",
    "vine_end",
)


@dataclass(frozen=True)
class PlotAssignment:
    """One whole plot, with 1-based inclusive row and vine coordinates."""

    block: int
    main_code: str
    sub_code: str
    plot_id: str
    row_start: int
    row_end: int
    vine_start: int
    vine_end: int

    def as_csv_row(self) -> tuple[str, ...]:
        return (
            str(self.block),
            self.main_code,
            self.sub_code,
            self.plot_id,
            str(self.row_start),
            str(self.row_end),
            str(self.vine_start),
            str(self.vine_end),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "block": self.block,
            "main_code": self.main_code,
            "sub_code": self.sub_code,
            "plot_id": self.plot_id,
            "row_start": self.row_start,
            "row_end": self.row_end,
            "vine_start": self.vine_start,
            "vine_end": self.vine_end,
        }


@dataclass(frozen=True)
class DesignResult:
    output_dir: Path
    files: tuple[Path, ...]
    digest: str
    total_rows: int
    field_length_m: float
    field_width_m: float
    plots: int


def total_field_rows(config: DesignConfig) -> int:
    """Rows occupied by plots plus all buffers, including block separators."""

    layout = config.layout
    return config.blocks * layout.rows_per_plot + (config.blocks - 1) * layout.buffer_rows


def randomize(config: DesignConfig, seed: int) -> list[PlotAssignment]:
    """Return the full allocation.

    Blocks are complete. Inside each block the main plots are shuffled, and
    inside each main plot the sub plots are shuffled independently. One RNG
    stream feeds everything, so a seed alone reproduces the whole layout.
    """

    rng = random.Random(seed)
    layout = config.layout
    sub_levels: tuple[Level, ...] = config.sub_levels
    main_levels: tuple[Level, ...] = config.main_levels
    assignments: list[PlotAssignment] = []
    row_cursor = 1

    for block in range(1, config.blocks + 1):
        if block > 1:
            row_cursor += layout.buffer_rows
        row_start = row_cursor
        row_end = row_start + layout.rows_per_plot - 1
        shuffled_main = list(main_levels)
        rng.shuffle(shuffled_main)
        for main_position, main_level in enumerate(shuffled_main, start=1):
            shuffled_sub = list(sub_levels)
            rng.shuffle(shuffled_sub)
            for sub_position, sub_level in enumerate(shuffled_sub, start=1):
                vine_start = (
                    (main_position - 1) * len(shuffled_sub) + (sub_position - 1)
                ) * layout.vines_per_row + 1
                vine_end = vine_start + layout.vines_per_row - 1
                plot_id = f"B{block:02d}-M{main_position:02d}-S{sub_position:02d}"
                assignments.append(
                    PlotAssignment(
                        block=block,
                        main_code=main_level.code,
                        sub_code=sub_level.code,
                        plot_id=plot_id,
                        row_start=row_start,
                        row_end=row_end,
                        vine_start=vine_start,
                        vine_end=vine_end,
                    )
                )
        row_cursor = row_end + 1

    assignment_rows = total_field_rows(config)
    last = assignments[-1]
    if last.row_end != assignment_rows:
        raise AssertionError("internal geometry error: row cursor mismatch")
    return assignments


def allocation_digest(assignments: Iterable[PlotAssignment]) -> str:
    payload = "\n".join(",".join(row.as_csv_row()) for row in assignments)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ensure_output_dir(output_dir: Path, force: bool) -> None:
    if output_dir.exists():
        if not output_dir.is_dir():
            raise OutputError("输出路径已存在且不是目录 (output path is not a directory)",
                              path=output_dir)
        if any(output_dir.iterdir()) and not force:
            raise OutputError(
                "输出目录非空；加 --force 覆盖 (output directory not empty; use --force)",
                path=output_dir,
            )
    else:
        output_dir.mkdir(parents=True)


def _write_allocation(path: Path, assignments: list[PlotAssignment]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        for assignment in assignments:
            writer.writerow(assignment.as_csv_row())


def _payload(config: DesignConfig, seed: int, assignments: list[PlotAssignment],
             digest: str, total_rows: int) -> dict[str, object]:
    layout = config.layout
    return {
        "schema_version": SCHEMA_VERSION,
        "design": "split-plot in randomized complete blocks",
        "seed": seed,
        "title": config.title,
        "blocks": config.blocks,
        "statistical_unit": "plot",
        "main_plot": {
            "name": config.main_plot_name,
            "levels": [{"code": level.code, "label": level.label}
                       for level in config.main_levels],
        },
        "sub_plot": {
            "name": config.sub_plot_name,
            "levels": [{"code": level.code, "label": level.label}
                       for level in config.sub_levels],
        },
        "layout": {
            "plot_length_m": layout.plot_length_m,
            "plot_width_m": layout.plot_width_m,
            "rows_per_plot": layout.rows_per_plot,
            "vines_per_row": layout.vines_per_row,
            "buffer_rows": layout.buffer_rows,
            "row_spacing_m": layout.row_spacing_m,
            "vine_spacing_m": layout.vine_spacing_m,
            "plot_area_m2": round(layout.plot_area_m2, 3),
            "vines_per_plot": layout.vines_per_plot,
            "field_length_m": round(layout.vines_per_row * config.plots_per_block
                                    * layout.vine_spacing_m, 2),
            "field_width_m": round(total_rows * layout.row_spacing_m, 2),
            "total_rows": total_rows,
        },
        "sampling": {
            "points_per_plot": config.sampling.points_per_plot,
            "treated_as": config.sampling.treated_as,
        },
        "randomization": {
            "procedure": "Fully randomize main plots within each block, then sub plots "
                         "within each main plot; blocks stay complete.",
            "rng": "Python random.Random (Mersenne Twister), single stream",
            "reproducible_with_seed": True,
        },
        "allocation_digest_sha256": digest,
        "allocation": [assignment.as_dict() for assignment in assignments],
    }


def write_design(
    config: DesignConfig,
    output_dir: Path,
    *,
    seed: int | None = None,
    force: bool = False,
    formats: tuple[str, ...] = ("png", "svg"),
) -> DesignResult:
    """Randomize, write CSV/JSON, and render the field map."""

    chosen_seed = config.seed if seed is None else seed
    if not 0 <= chosen_seed <= 2**32 - 1:
        raise OutputError("seed 必须在 0..4294967295 之间 (seed out of range)")

    output_dir = output_dir.resolve()
    _ensure_output_dir(output_dir, force)

    assignments = randomize(config, chosen_seed)
    digest = allocation_digest(assignments)
    total_rows = total_field_rows(config)

    allocation_path = output_dir / "allocation.csv"
    design_path = output_dir / "design.json"
    _write_allocation(allocation_path, assignments)
    design_path.write_text(
        json.dumps(_payload(config, chosen_seed, assignments, digest, total_rows),
                   ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )

    files: list[Path] = [allocation_path, design_path]
    files.extend(render_field_map(config, assignments, total_rows, output_dir, formats))

    return DesignResult(
        output_dir=output_dir,
        files=tuple(files),
        digest=digest,
        total_rows=total_rows,
        field_length_m=config.layout.vines_per_row * config.plots_per_block
        * config.layout.vine_spacing_m,
        field_width_m=total_rows * config.layout.row_spacing_m,
        plots=len(assignments),
    )
