"""``splitplot`` command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from splitplot_designer import __version__
from splitplot_designer.config import template_text
from splitplot_designer.design import write_design
from splitplot_designer.errors import OutputError, SplitplotError
from splitplot_designer.methods import build_methods_text
from splitplot_designer.models import build_model_text
from splitplot_designer.power import DEFAULT_SEED, format_report, simulate_power
from splitplot_designer.validate import load_config, validate_file

PROGRAM = "splitplot"
DESCRIPTION = """\
裂区试验设计工具 / split-plot design toolkit

工作流 / workflow:
  splitplot init     生成带注释的配置 / write an annotated starter config
  splitplot validate 校验配置与几何 / validate structure and geometry
  splitplot design   可复现随机化并出图 / randomize reproducibly and render
  splitplot power    蒙特卡洛功效模拟 / Monte Carlo power simulation
  splitplot model    输出正确误差分层的模型 / correct error-strata formulas
  splitplot methods  生成方法段草稿 / draft a methods paragraph

只支持随机完全区组裂区设计。示例数据为合成演示。
Only randomized complete block split-plot designs are supported. Examples are synthetic.
"""


def _seed(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seed 必须是整数 / seed must be an integer") from exc
    if not 0 <= parsed <= 2**32 - 1:
        raise argparse.ArgumentTypeError("seed 必须在 0..4294967295 / seed out of range")
    return parsed


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是整数 / must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("必须 >= 1 / must be >= 1")
    return parsed


def _formats(value: str) -> tuple[str, ...]:
    items = tuple(item.strip().lower() for item in value.split(",") if item.strip())
    unknown = sorted(set(items) - {"png", "svg"})
    if not items or unknown:
        raise argparse.ArgumentTypeError("格式只能是 png,svg / formats must be png,svg")
    return items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例 / example: splitplot design examples/vineyard_4blocks.yaml "
            "-o out --seed 20251117"
        ),
    )
    parser.add_argument("--version", action="version", version=f"{PROGRAM} {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="命令/command")

    init_parser = subparsers.add_parser(
        "init", help="生成带注释的示例配置 / write a commented starter config"
    )
    init_parser.add_argument("-o", "--output", default="design.yaml", type=Path,
                             help="输出文件，默认 design.yaml / output file")
    init_parser.add_argument("--force", action="store_true", help="覆盖已有文件 / overwrite")

    validate_parser = subparsers.add_parser(
        "validate", help="校验设计配置 / validate a design configuration"
    )
    validate_parser.add_argument("design", type=Path, help="YAML 配置文件 / config file")

    design_parser = subparsers.add_parser(
        "design", help="随机化并生成分配、JSON 与布局图 / randomize and render"
    )
    design_parser.add_argument("design", type=Path, help="YAML 配置文件 / config file")
    design_parser.add_argument("-o", "--output", required=True, type=Path,
                               help="输出目录 / output directory")
    design_parser.add_argument("--seed", type=_seed, default=None,
                               help="覆盖配置中的种子 / override the seed")
    design_parser.add_argument("--force", action="store_true",
                               help="允许写入非空目录 / allow a non-empty directory")
    design_parser.add_argument("--formats", type=_formats, default=("png", "svg"),
                               help="图形格式，默认 png,svg / map formats")

    power_parser = subparsers.add_parser(
        "power", help="蒙特卡洛功效与区组数建议 / power and block recommendation"
    )
    power_parser.add_argument("--blocks", type=_positive_int, default=4,
                              help="区组数，默认 4 / blocks")
    power_parser.add_argument("--effect", type=float, default=0.30,
                              help="Cohen's f（误差 SD=1），默认 0.30 / standardized effect")
    power_parser.add_argument("--icc", type=float, default=0.45,
                              help="主区误差方差占比，默认 0.45 / ICC")
    power_parser.add_argument("--alpha", type=float, default=0.05,
                              help="双侧 alpha，默认 0.05 / two-sided alpha")
    power_parser.add_argument("--main-levels", type=_positive_int, default=2,
                              help="主区水平数，默认 2 / main levels")
    power_parser.add_argument("--sub-levels", type=_positive_int, default=3,
                              help="副区水平数，默认 3 / sub levels")
    power_parser.add_argument("--sims", type=_positive_int, default=500,
                              help="模拟次数，默认 500 / simulations")
    power_parser.add_argument("--seed", type=_seed, default=DEFAULT_SEED,
                              help=f"模拟种子，默认 {DEFAULT_SEED} / simulation seed")
    power_parser.add_argument("--no-recommend", action="store_true",
                              help="跳过区组数搜索 / skip block search")
    power_parser.add_argument("-o", "--output", type=Path, default=None,
                              help="同时写出 JSON / also write JSON")

    model_parser = subparsers.add_parser(
        "model", help="输出 statsmodels 与 R 公式 / model formulas"
    )
    model_parser.add_argument("design", type=Path, help="YAML 配置文件 / config file")
    model_parser.add_argument("-o", "--output", type=Path, default=None,
                              help="写入文件而不是标准输出 / write a file")

    methods_parser = subparsers.add_parser(
        "methods", help="生成中文方法段草稿 / draft a Chinese methods paragraph"
    )
    methods_parser.add_argument("design", type=Path, help="YAML 配置文件 / config file")
    methods_parser.add_argument("-o", "--output", type=Path, default=None,
                                help="写入文件而不是标准输出 / write a file")

    return parser


def _run_init(args: argparse.Namespace) -> int:
    target: Path = args.output
    if target.exists() and not args.force:
        raise OutputError("文件已存在；加 --force 覆盖 (file exists; use --force)", path=target)
    if target.parent and not target.parent.exists():
        target.parent.mkdir(parents=True)
    target.write_text(template_text(), encoding="utf-8")
    print(f"已写入 / wrote: {target.resolve()}")
    print("下一步 / next: splitplot validate design.yaml && splitplot design design.yaml -o out")
    return 0


def _run_validate(args: argparse.Namespace) -> int:
    report = validate_file(args.design)
    if report.issues:
        print(report.render())
    if report.errors:
        print(
            f"\n失败 / failed: {len(report.errors)} 个错误, "
            f"{len(report.warnings)} 个警告 (errors, warnings)"
        )
        return 1
    print(
        f"\n通过 / passed: {len(report.warnings)} 个警告 (warnings)"
    )
    assert report.config is not None
    config = report.config
    print(
        f"结构 / structure: {config.blocks} 区组 × {len(config.main_levels)} 主区 × "
        f"{len(config.sub_levels)} 副区 = {config.total_plots} 小区"
    )
    print(
        "统计单元 / statistical unit: 小区 plot（不是单株或单个采样点） "
        "(plot, not vines or sampling points)"
    )
    if config.total_plots != config.blocks * config.plots_per_block:
        print("内部一致性 / internal check: 小区总数与结构不符", file=sys.stderr)
        return 1
    return 0


def _run_design(args: argparse.Namespace) -> int:
    config = load_config(args.design)
    result = write_design(
        config, args.output, seed=args.seed, force=args.force, formats=args.formats
    )
    print(f"输出目录 / output: {result.output_dir}")
    print(
        f"小区 / plots: {result.plots} · 行 / rows: {result.total_rows} · "
        f"田间尺寸 / field: {result.field_length_m:g} m × {result.field_width_m:g} m"
    )
    print(f"分配摘要 SHA-256 / allocation digest: {result.digest}")
    for path in result.files:
        print(f"  - {path.name}")
    print("统计单元 / statistical unit: 小区 plot_id（采样点是子样本，不是重复）")
    print("提示 / note: 图形与数据均为合成演示，替换配置后可生成本地设计。")
    return 0


def _run_power(args: argparse.Namespace) -> int:
    result = simulate_power(
        blocks=args.blocks,
        effect=args.effect,
        icc=args.icc,
        alpha=args.alpha,
        main_levels=args.main_levels,
        sub_levels=args.sub_levels,
        sims=args.sims,
        seed=args.seed,
        recommend=not args.no_recommend,
    )
    print(format_report(result))
    if args.output is not None:
        import json

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result.as_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nJSON 已写入 / wrote: {args.output.resolve()}")
    return 0


def _write_or_print(text: str, output: Path | None) -> int:
    if output is None:
        print(text)
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print(f"已写入 / wrote: {output.resolve()}")
    return 0


def _run_model(args: argparse.Namespace) -> int:
    return _write_or_print(build_model_text(load_config(args.design)), args.output)


def _run_methods(args: argparse.Namespace) -> int:
    return _write_or_print(build_methods_text(load_config(args.design)), args.output)


HANDLERS = {
    "init": _run_init,
    "validate": _run_validate,
    "design": _run_design,
    "power": _run_power,
    "model": _run_model,
    "methods": _run_methods,
}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return HANDLERS[args.command](args)
    except SplitplotError as exc:
        print(f"错误 / error: {exc.render()}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"错误 / error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n已中断 / interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
