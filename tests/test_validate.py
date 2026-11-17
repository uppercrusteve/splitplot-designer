"""Validation diagnostics: line numbers, severities, and hard errors."""

from __future__ import annotations

from pathlib import Path

import pytest

from splitplot_designer.errors import ConfigError
from splitplot_designer.validate import load_config, validate_file


def messages(report) -> str:
    return report.render()


def test_valid_example_passes(yaml_file) -> None:
    report = validate_file(yaml_file())
    assert report.ok, messages(report)
    assert report.errors == []
    assert report.config is not None
    assert report.config.total_plots == 16


def test_missing_file_is_an_error(tmp_path: Path) -> None:
    report = validate_file(tmp_path / "absent.yaml")
    assert not report.ok
    assert "not found" in messages(report)


def test_two_blocks_rejected(yaml_file) -> None:
    report = validate_file(yaml_file(blocks=2))
    assert not report.ok
    assert "at least 3 blocks" in messages(report)


def test_zero_buffer_rejected(yaml_file) -> None:
    report = validate_file(yaml_file(buffer=0))
    assert not report.ok
    assert "buffer rows must be >= 1" in messages(report)


def test_plot_length_mismatch_rejected(yaml_file) -> None:
    report = validate_file(yaml_file(length=24))
    assert not report.ok
    assert "disagrees with vine geometry" in messages(report)


def test_plot_length_within_tolerance_is_accepted(yaml_file) -> None:
    report = validate_file(yaml_file(length=20.8))
    assert report.ok, messages(report)


def test_seed_out_of_range_rejected(yaml_file) -> None:
    report = validate_file(yaml_file(seed=2**32))
    assert not report.ok
    assert "seed out of range" in messages(report)


def test_duplicate_code_is_reported_with_first_line(yaml_file) -> None:
    path = yaml_file()
    text = path.read_text(encoding="utf-8").replace("{code: NG, label: 自然生草}", "{code: CK, label: 重复}")
    path.write_text(text, encoding="utf-8")
    report = validate_file(path)
    assert not report.ok
    rendered = messages(report)
    assert "duplicate code `CK`" in rendered
    assert "first used on line" in rendered


def test_illegal_code_characters_rejected(yaml_file) -> None:
    path = yaml_file()
    text = path.read_text(encoding="utf-8").replace("code: NG", "code: 2NG")
    path.write_text(text, encoding="utf-8")
    report = validate_file(path)
    assert not report.ok
    assert "must start with a letter" in messages(report)


def test_subsamples_marked_as_replicates_warn(yaml_file) -> None:
    path = yaml_file()
    text = path.read_text(encoding="utf-8").replace("points_per_plot: 1", "points_per_plot: 3")
    text = text.replace("treated_as: plot_mean", "treated_as: replicates")
    path.write_text(text, encoding="utf-8")
    report = validate_file(path)
    assert report.ok
    rendered = messages(report)
    assert "warning" in rendered
    assert "pseudo-replication" in rendered


def test_unknown_top_level_key_warns(yaml_file) -> None:
    path = yaml_file()
    path.write_text(path.read_text(encoding="utf-8") + "extra: 1\n", encoding="utf-8")
    report = validate_file(path)
    assert report.ok
    assert "unknown top-level key" in messages(report)


def test_same_factor_name_rejected(yaml_file) -> None:
    path = yaml_file()
    text = path.read_text(encoding="utf-8").replace("name: canopy", "name: floor")
    path.write_text(text, encoding="utf-8")
    report = validate_file(path)
    assert not report.ok
    assert "must differ" in messages(report)


def test_load_config_raises_with_location(yaml_file) -> None:
    path = yaml_file(blocks=1)
    with pytest.raises(ConfigError) as excinfo:
        load_config(path)
    assert str(path) in excinfo.value.render()
    assert "validation failed" in str(excinfo.value)


def test_issue_render_includes_line_and_severity(yaml_file) -> None:
    report = validate_file(yaml_file(blocks=2))
    issue = report.errors[0]
    rendered = issue.render(report.path)
    assert "error" in rendered
    assert f":{issue.line}:" in rendered
