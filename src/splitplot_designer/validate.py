"""Configuration validation with line-numbered, bilingual diagnostics.

Validation is deliberately strict about the properties that make a split-plot
field book auditable: treatment structure, replication, unique codes, buffer
rows, and the agreement between declared plot geometry and row/vine counts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from splitplot_designer.config import (
    CODE_PATTERN,
    TREATMENT_UNITS,
    DesignConfig,
    build_config,
)
from splitplot_designer.errors import ConfigError

Severity = Literal["error", "warning"]

KNOWN_EXPERIMENT_KEYS = {
    "title",
    "blocks",
    "main_plot",
    "sub_plot",
    "layout",
    "sampling",
    "seed",
}
EXPECTED_LAYOUT_KEYS = {
    "plot_length_m",
    "plot_width_m",
    "rows_per_plot",
    "vines_per_row",
    "buffer_rows",
    "row_spacing_m",
    "vine_spacing_m",
}
GEOMETRY_TOLERANCE = 0.05
MAX_SEED = 2**32 - 1


@dataclass(frozen=True)
class Issue:
    """A single diagnostic anchored to a source line."""

    severity: Severity
    line: int
    message: str
    hint: str = ""

    def render(self, path: Path) -> str:
        label = "错误/error" if self.severity == "error" else "警告/warning"
        text = f"{path}:{self.line}: {label}: {self.message}"
        if self.hint:
            text += f"\n    提示/hint: {self.hint}"
        return text


@dataclass
class ValidationReport:
    path: Path
    issues: list[Issue] = field(default_factory=list)
    config: DesignConfig | None = None

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def sorted_issues(self) -> list[Issue]:
        return sorted(self.issues, key=lambda issue: (issue.line, issue.severity))

    def render(self) -> str:
        return "\n".join(issue.render(self.path) for issue in self.sorted_issues())


class _Collector:
    def __init__(self, path: Path, lines: dict[str, int]) -> None:
        self.path = path
        self.lines = lines
        self.issues: list[Issue] = []

    def line(self, path: str, fallback: int = 1) -> int:
        return self.lines.get(path, fallback)

    def error(self, path: str, message: str, hint: str = "") -> None:
        self.issues.append(Issue("error", self.line(path), message, hint))

    def warning(self, path: str, message: str, hint: str = "") -> None:
        self.issues.append(Issue("warning", self.line(path), message, hint))


def _collect_lines(node: yaml.Node, prefix: str, out: dict[str, int]) -> None:
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            key = str(key_node.value)
            path = f"{prefix}.{key}" if prefix else key
            out[path] = key_node.start_mark.line + 1
            _collect_lines(value_node, path, out)
    elif isinstance(node, yaml.SequenceNode):
        for index, item in enumerate(node.value):
            path = f"{prefix}[{index}]"
            out[path] = item.start_mark.line + 1
            _collect_lines(item, path, out)


def _load_document(path: Path) -> tuple[Any, dict[str, int]]:
    if not path.exists():
        raise ConfigError("配置文件不存在 (configuration file not found)", path=path)
    if path.is_dir():
        raise ConfigError("路径是目录，不是文件 (path is a directory)", path=path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigError("文件不是 UTF-8 编码 (file is not UTF-8)", path=path) from exc
    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
        line = mark.line + 1 if mark is not None else 1
        problem = getattr(exc, "problem", None) or "无法解析 (cannot parse)"
        raise ConfigError(
            f"YAML 语法错误 (YAML syntax error): {problem}", path=path, line=line
        ) from exc
    lines: dict[str, int] = {}
    if node is not None:
        _collect_lines(node, "", lines)
    return data, lines


def _check_levels(
    collector: _Collector,
    section: dict[str, Any],
    section_path: str,
) -> list[tuple[str, str]]:
    """Validate one treatment factor and return ``(code, line)`` pairs."""

    raw_levels = section.get("levels")
    if not isinstance(raw_levels, list):
        collector.error(f"{section_path}.levels", "`levels` 必须是列表 (must be a list)")
        return []
    if len(raw_levels) < 2:
        collector.error(
            f"{section_path}.levels",
            f"{section_path} 至少需要 2 个水平，当前 {len(raw_levels)} 个 "
            f"(at least 2 levels required, got {len(raw_levels)})",
        )

    seen: dict[str, int] = {}
    pairs: list[tuple[str, str]] = []
    for index, item in enumerate(raw_levels):
        item_path = f"{section_path}.levels[{index}]"
        if not isinstance(item, dict):
            collector.error(item_path, "水平必须是映射 (level must be a mapping)")
            continue
        code = item.get("code")
        label = item.get("label")
        code_path = f"{item_path}.code"
        label_path = f"{item_path}.label"

        if not isinstance(code, str) or not code.strip():
            collector.error(code_path, "编码不能为空 (code must be non-empty)")
            code = ""
        else:
            code = code.strip()
            if code in seen:
                collector.error(
                    code_path,
                    f"编码 `{code}` 重复，首次出现于第 {seen[code]} 行 "
                    f"(duplicate code `{code}`, first used on line {seen[code]})",
                )
            else:
                seen[code] = collector.line(code_path)
            if not CODE_PATTERN.fullmatch(code):
                collector.error(
                    code_path,
                    f"编码 `{code}` 只能用字母开头及字母/数字/下划线/连字符，最长 12 字符 "
                    f"(code must start with a letter and use only ASCII word characters, max 12)",
                )
        if not isinstance(label, str) or not label.strip():
            collector.error(label_path, "显示名称不能为空 (label must be non-empty)")
        elif len(label) > 40:
            collector.warning(label_path, "显示名称超过 40 字符，图上可能拥挤 "
                              "(label longer than 40 characters)")
        pairs.append((code, collector.line(code_path)))
    return pairs


def _check_layout(
    collector: _Collector, layout: dict[str, Any], layout_path: str
) -> None:
    for key in EXPECTED_LAYOUT_KEYS:
        if key not in layout:
            collector.error(f"{layout_path}.{key}", f"缺少 `{key}` (missing `{key}`)")
    for key in sorted(layout):
        if key not in EXPECTED_LAYOUT_KEYS:
            collector.warning(
                f"{layout_path}.{key}", f"未知字段 `{key}`，将被忽略 (unknown key, ignored)"
            )

    int_fields = ("rows_per_plot", "vines_per_row", "buffer_rows")
    float_fields = ("plot_length_m", "plot_width_m", "row_spacing_m", "vine_spacing_m")
    for key in int_fields:
        value = layout.get(key)
        field_path = f"{layout_path}.{key}"
        if isinstance(value, bool) or not isinstance(value, int):
            collector.error(field_path, f"`{key}` 必须是整数 (must be an integer)")
    for key in float_fields:
        value = layout.get(key)
        field_path = f"{layout_path}.{key}"
        if isinstance(value, bool) or not isinstance(value, int | float):
            collector.error(field_path, f"`{key}` 必须是数字 (must be a number)")
        elif value <= 0:
            collector.error(field_path, f"`{key}` 必须 > 0 (must be > 0)")

    rows = layout.get("rows_per_plot")
    vines = layout.get("vines_per_row")
    buffer_rows = layout.get("buffer_rows")
    if isinstance(rows, int) and not isinstance(rows, bool) and rows < 1:
        collector.error(f"{layout_path}.rows_per_plot", "每小区行数必须 >= 1 (must be >= 1)")
    if isinstance(vines, int) and not isinstance(vines, bool) and vines < 1:
        collector.error(f"{layout_path}.vines_per_row", "每行株数必须 >= 1 (must be >= 1)")
    if isinstance(buffer_rows, int) and not isinstance(buffer_rows, bool) and buffer_rows < 1:
        collector.error(
            f"{layout_path}.buffer_rows",
            f"缓冲行必须 >= 1，当前 {buffer_rows} (buffer rows must be >= 1)",
            hint="缓冲行用于隔离相邻小区，至少保留 1 行。",
        )

    length = layout.get("plot_length_m")
    width = layout.get("plot_width_m")
    row_spacing = layout.get("row_spacing_m")
    vine_spacing = layout.get("vine_spacing_m")
    if (
        isinstance(vines, int)
        and not isinstance(vines, bool)
        and isinstance(vine_spacing, int | float)
        and not isinstance(vine_spacing, bool)
        and isinstance(length, int | float)
        and not isinstance(length, bool)
        and vine_spacing > 0
    ):
        expected = vines * vine_spacing
        if abs(length - expected) > max(GEOMETRY_TOLERANCE * expected, 0.05):
            collector.error(
                f"{layout_path}.plot_length_m",
                f"小区长 {length:g} m 与 {vines} 株 × {vine_spacing:g} m/株 "
                f"= {expected:g} m 不一致 "
                f"(plot length disagrees with vine geometry)",
                hint="沿行向长度必须等于每行株数乘以株距（容差 5%）。",
            )
    if (
        isinstance(rows, int)
        and not isinstance(rows, bool)
        and isinstance(row_spacing, int | float)
        and not isinstance(row_spacing, bool)
        and isinstance(width, int | float)
        and not isinstance(width, bool)
        and row_spacing > 0
    ):
        expected = rows * row_spacing
        if abs(width - expected) > max(GEOMETRY_TOLERANCE * expected, 0.05):
            collector.error(
                f"{layout_path}.plot_width_m",
                f"小区宽 {width:g} m 与 {rows} 行 × {row_spacing:g} m/行 = {expected:g} m 不一致 "
                f"(plot width disagrees with row geometry)",
                hint="跨行向宽度必须等于行数乘以行距（容差 5%）。",
            )


def validate_data(data: Any, lines: dict[str, int], path: Path) -> ValidationReport:
    """Validate an already-parsed document and return a report."""

    collector = _Collector(path, lines)
    report = ValidationReport(path=path, issues=collector.issues)

    if data is None:
        collector.error("", "配置为空 (empty configuration)")
        return report
    if not isinstance(data, dict):
        collector.error("", "根节点必须是映射 (root must be a mapping)")
        return report

    for key in sorted(data):
        if key != "experiment":
            collector.warning(key, f"未知顶层字段 `{key}`，将被忽略 (unknown top-level key)")

    experiment = data.get("experiment")
    if not isinstance(experiment, dict):
        collector.error("experiment", "缺少 `experiment` 映射 (missing `experiment` mapping)")
        return report

    for key in sorted(experiment):
        if key not in KNOWN_EXPERIMENT_KEYS:
            collector.warning(
                f"experiment.{key}", f"未知字段 `{key}`，将被忽略 (unknown key, ignored)"
            )

    title = experiment.get("title")
    if not isinstance(title, str) or not title.strip():
        collector.error("experiment.title", "试验标题不能为空 (title must be non-empty)")

    blocks = experiment.get("blocks")
    if "blocks" not in experiment:
        collector.error("experiment.blocks", "缺少 `blocks` (missing `blocks`)")
    elif isinstance(blocks, bool) or not isinstance(blocks, int):
        collector.error("experiment.blocks", "`blocks` 必须是整数 (must be an integer)")
    elif blocks < 3:
        collector.error(
            "experiment.blocks",
            f"区组数必须 >= 3，当前 {blocks} (at least 3 blocks required, got {blocks})",
            hint="裂区试验至少需要 3 个完整区组才能估计主区误差。",
        )
    elif blocks > 10:
        collector.warning(
            "experiment.blocks",
            f"{blocks} 个区组会让布局图很高，建议分页或分段打印 "
            f"(many blocks make a tall map; print in sections)",
        )

    seed = experiment.get("seed")
    if "seed" not in experiment:
        collector.error("experiment.seed", "缺少 `seed` (missing `seed`)")
    elif isinstance(seed, bool) or not isinstance(seed, int):
        collector.error("experiment.seed", "`seed` 必须是整数 (must be an integer)")
    elif not 0 <= seed <= MAX_SEED:
        collector.error(
            "experiment.seed", f"`seed` 必须在 0..{MAX_SEED} 之间 (seed out of range)"
        )

    main = experiment.get("main_plot")
    sub = experiment.get("sub_plot")
    main_pairs: list[tuple[str, str]] = []
    sub_pairs: list[tuple[str, str]] = []

    if not isinstance(main, dict):
        collector.error("experiment.main_plot", "缺少 `main_plot` 映射 (missing `main_plot`)")
    else:
        for key in sorted(main):
            if key not in {"name", "levels"}:
                collector.warning(
                    "experiment.main_plot." + key, f"未知字段 `{key}`，将被忽略 (unknown key)"
                )
        name = main.get("name")
        if not isinstance(name, str) or not name.strip():
            collector.error("experiment.main_plot.name", "主区因子名不能为空 (name required)")
        main_pairs = _check_levels(collector, main, "experiment.main_plot")

    if not isinstance(sub, dict):
        collector.error("experiment.sub_plot", "缺少 `sub_plot` 映射 (missing `sub_plot`)")
    else:
        for key in sorted(sub):
            if key not in {"name", "levels"}:
                collector.warning(
                    "experiment.sub_plot." + key, f"未知字段 `{key}`，将被忽略 (unknown key)"
                )
        name = sub.get("name")
        if not isinstance(name, str) or not name.strip():
            collector.error("experiment.sub_plot.name", "副区因子名不能为空 (name required)")
        sub_pairs = _check_levels(collector, sub, "experiment.sub_plot")

    main_name = main.get("name") if isinstance(main, dict) else None
    sub_name = sub.get("name") if isinstance(sub, dict) else None
    if (
        isinstance(main_name, str)
        and isinstance(sub_name, str)
        and main_name.strip()
        and main_name.strip() == sub_name.strip()
    ):
        collector.error(
            "experiment.sub_plot.name",
            "主区与副区因子名相同，模型公式会歧义 "
            "(main and sub factor names must differ)",
        )

    main_codes = {code for code, _ in main_pairs if code}
    sub_codes = {code for code, _ in sub_pairs if code}
    overlap = sorted(main_codes & sub_codes)
    if overlap:
        collector.warning(
            "experiment.sub_plot.levels",
            f"主区与副区使用了相同编码 {', '.join(overlap)}，报告里需注明因子 "
            f"(codes reused across factors; always qualify by factor)",
        )

    layout = experiment.get("layout")
    if not isinstance(layout, dict):
        collector.error("experiment.layout", "缺少 `layout` 映射 (missing `layout`)")
    else:
        _check_layout(collector, layout, "experiment.layout")

    sampling = experiment.get("sampling")
    points = 1
    treated = "plot_mean"
    if sampling is not None:
        if not isinstance(sampling, dict):
            collector.error("experiment.sampling", "`sampling` 必须是映射 (must be a mapping)")
        else:
            for key in sorted(sampling):
                if key not in {"points_per_plot", "treated_as"}:
                    collector.warning(
                        "experiment.sampling." + key, f"未知字段 `{key}` (unknown key)"
                    )
            points = sampling.get("points_per_plot", 1)
            treated = sampling.get("treated_as", "plot_mean")
            if isinstance(points, bool) or not isinstance(points, int):
                collector.error(
                    "experiment.sampling.points_per_plot", "采样点数必须是整数 (must be an integer)"
                )
                points = 1
            elif points < 1:
                collector.error(
                    "experiment.sampling.points_per_plot", "采样点数必须 >= 1 (must be >= 1)"
                )
            if treated not in TREATMENT_UNITS:
                collector.error(
                    "experiment.sampling.treated_as",
                    f"`treated_as` 必须是 {', '.join(TREATMENT_UNITS)} 之一 (invalid value)",
                )
                treated = "plot_mean"

    if points > 1:
        if treated == "replicates":
            collector.warning(
                "experiment.sampling.treated_as",
                f"每小区 {points} 个采样点被当作重复：存在伪重复风险 "
                f"(subsamples treated as replicates: pseudo-replication risk)",
                hint="同一小区的采样点不独立；应先用小区均值，或在混合模型中加小区随机效应，"
                "并把 df 按小区计算。",
            )
        else:
            collector.warning(
                "experiment.sampling.points_per_plot",
                f"每小区 {points} 个采样点；统计单元应是小区的均值，而不是单个采样点 "
                f"(statistical unit is the plot mean, not an individual sample)",
                hint="analysis.csv 中请按 plot_id 聚合后再进模型。",
            )
    elif treated == "replicates" and points == 1:
        collector.warning(
            "experiment.sampling.treated_as",
            "只有 1 个采样点却标记为 replicates，等价于 plot_mean "
            "(single sample per plot; replicates is redundant)",
        )

    report.issues = collector.issues
    if report.ok:
        try:
            report.config = build_config(data, lines, path)
        except ConfigError as exc:
            report.issues.append(Issue("error", exc.line or 1, exc.message))
    return report


def validate_file(path: Path) -> ValidationReport:
    """Parse and validate ``path``; never raises for ordinary bad input."""

    try:
        data, lines = _load_document(path)
    except ConfigError as exc:
        return ValidationReport(
            path=path,
            issues=[Issue("error", exc.line or 1, exc.message)],
        )
    return validate_data(data, lines, path)


def load_config(path: Path) -> DesignConfig:
    """Return a validated config or raise :class:`ConfigError` with diagnostics."""

    report = validate_file(path)
    if not report.ok or report.config is None:
        rendered = report.render() or f"{path}: 配置无效 (invalid configuration)"
        raise ConfigError(f"配置校验失败 (validation failed)\n{rendered}", path=path)
    return report.config
