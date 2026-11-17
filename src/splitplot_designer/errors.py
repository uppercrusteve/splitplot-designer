"""Shared exception types.

User-facing failures carry a bilingual message and an optional source line so the
CLI can print a location in ``file:line:`` style.
"""

from __future__ import annotations

from pathlib import Path


class SplitplotError(Exception):
    """Base class for expected, user-facing failures."""

    def __init__(self, message: str, *, path: Path | None = None, line: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.path = path
        self.line = line

    def render(self) -> str:
        prefix = ""
        if self.path is not None:
            prefix = str(self.path)
            if self.line is not None:
                prefix = f"{prefix}:{self.line}"
        return f"{prefix}: {self.message}" if prefix else self.message


class ConfigError(SplitplotError):
    """The configuration file cannot be parsed or is structurally invalid."""


class OutputError(SplitplotError):
    """An output directory or file cannot be used safely."""
