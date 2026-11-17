"""End-to-end CLI behaviour, exit codes, and rendered artifacts."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "splitplot_designer", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def test_help_lists_every_command() -> None:
    completed = run_cli("--help")
    assert completed.returncode == 0
    for command in ("init", "validate", "design", "power", "model", "methods"):
        assert command in completed.stdout


def test_version_exits_zero() -> None:
    completed = run_cli("--version")
    assert completed.returncode == 0
    assert "0.1.0" in completed.stdout


def test_init_writes_commented_template(tmp_path: Path) -> None:
    target = tmp_path / "starter.yaml"
    completed = run_cli("init", "-o", str(target))
    assert completed.returncode == 0
    text = target.read_text(encoding="utf-8")
    assert "synthetic" in text
    assert "blocks" in text


def test_validate_reports_ok(tmp_path: Path) -> None:
    source = tmp_path / "ok.yaml"
    assert run_cli("init", "-o", str(source)).returncode == 0
    completed = run_cli("validate", str(source))
    assert completed.returncode == 0
    assert "通过" in completed.stdout


def test_validate_bad_config_exits_nonzero(tmp_path: Path) -> None:
    source = tmp_path / "bad.yaml"
    source.write_text("experiment:\n  title: x\n", encoding="utf-8")
    completed = run_cli("validate", str(source))
    assert completed.returncode != 0
    assert "error" in completed.stdout
    assert "failed" in completed.stdout


def test_design_writes_all_outputs(tmp_path: Path) -> None:
    source = tmp_path / "ok.yaml"
    assert run_cli("init", "-o", str(source)).returncode == 0
    output = tmp_path / "out"
    completed = run_cli("design", str(source), "-o", str(output))
    assert completed.returncode == 0, completed.stderr
    for name, minimum in (
        ("allocation.csv", 300),
        ("design.json", 500),
        ("field-map.png", 5000),
        ("field-map.svg", 5000),
    ):
        target = output / name
        assert target.is_file(), name
        assert target.stat().st_size > minimum, name


def test_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    source = tmp_path / "ok.yaml"
    assert run_cli("init", "-o", str(source)).returncode == 0
    output = tmp_path / "out"
    assert run_cli("design", str(source), "-o", str(output)).returncode == 0
    again = run_cli("design", str(source), "-o", str(output))
    assert again.returncode != 0
    assert "--force" in again.stderr
    forced = run_cli("design", str(source), "-o", str(output), "--force")
    assert forced.returncode == 0


def test_power_runs_and_prints_disclaimer() -> None:
    completed = run_cli("power", "--blocks", "4", "--effect", "0.6", "--sims", "40")
    assert completed.returncode == 0, completed.stderr
    assert "power" in completed.stdout.lower()


@pytest.mark.parametrize(
    ("argument", "value", "expected"),
    [
        ("--blocks", "1", "blocks must be >= 2"),
        ("--effect", "5", "effect must be within"),
        ("--icc", "2", "icc must be in"),
        ("--sims", "3", "sims must be >= 10"),
    ],
)
def test_power_rejects_out_of_range(argument: str, value: str, expected: str) -> None:
    completed = run_cli("power", argument, value)
    assert completed.returncode != 0
    assert expected in completed.stderr
