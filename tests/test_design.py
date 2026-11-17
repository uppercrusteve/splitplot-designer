"""Randomization reproducibility and field-geometry invariants."""

from __future__ import annotations

from collections import Counter

from splitplot_designer.design import (
    allocation_digest,
    randomize,
    total_field_rows,
)


def test_same_seed_reproduces_identical_allocation(config) -> None:
    first = randomize(config, 7)
    second = randomize(config, 7)
    assert [plot.as_dict() for plot in first] == [plot.as_dict() for plot in second]
    assert allocation_digest(first) == allocation_digest(second)


def test_different_seed_changes_allocation(config) -> None:
    assert allocation_digest(randomize(config, 7)) != allocation_digest(randomize(config, 8))


def test_every_block_is_complete_and_balanced(config) -> None:
    plots = randomize(config, 11)
    assert len(plots) == config.total_plots == 24
    per_block = Counter(plot.block for plot in plots)
    assert per_block == {block: 6 for block in range(1, config.blocks + 1)}
    for block in range(1, config.blocks + 1):
        pairs = {(plot.main_code, plot.sub_code) for plot in plots if plot.block == block}
        assert len(pairs) == len(config.main_levels) * len(config.sub_levels)


def test_main_levels_appear_once_per_block(config) -> None:
    plots = randomize(config, 3)
    for block in range(1, config.blocks + 1):
        codes = [plot.main_code for plot in plots if plot.block == block]
        assert Counter(codes) == {level.code: len(config.sub_levels) for level in config.main_levels}


def test_plot_ids_are_unique(config) -> None:
    plots = randomize(config, 5)
    assert len({plot.plot_id for plot in plots}) == len(plots)


def test_plot_rows_do_not_overlap(config) -> None:
    plots = randomize(config, 13)
    by_block: dict[int, list[tuple[int, int]]] = {}
    for plot in plots:
        by_block.setdefault(plot.block, []).append((plot.row_start, plot.row_end))
    for spans in by_block.values():
        assert len(set(spans)) == 1, "all sub plots of a main plot share one row span"
    ordered = sorted({span for spans in by_block.values() for span in spans})
    for (_, end), (start, _) in zip(ordered, ordered[1:], strict=False):
        assert start > end, "blocks must be separated by at least one buffer row"


def test_plot_vines_stay_inside_the_field(config) -> None:
    plots = randomize(config, 17)
    field_vines = config.layout.vines_per_row * config.plots_per_block
    field_rows = total_field_rows(config)
    for plot in plots:
        assert 1 <= plot.vine_start <= plot.vine_end <= field_vines
        assert 1 <= plot.row_start <= plot.row_end <= field_rows
        assert plot.vine_end - plot.vine_start + 1 == config.layout.vines_per_row
        assert plot.row_end - plot.row_start + 1 == config.layout.rows_per_plot


def test_one_block_occupies_one_row_span(config) -> None:
    plots = [plot for plot in randomize(config, 19) if plot.block == 1]
    assert len({plot.row_start for plot in plots}) == 1
    assert len({plot.row_end for plot in plots}) == 1
    assert len({plot.vine_start for plot in plots}) == len(plots)
