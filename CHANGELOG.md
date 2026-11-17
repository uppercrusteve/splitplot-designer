# Changelog

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-11-17

首个可运行版本。

### Added

- `splitplot init`：生成带注释的合成配置模板。
- `splitplot validate`：按 `文件:行号` 输出中英双语诊断；校验区组数 `>= 3`、缓冲行 `>= 1`、种子范围、水平数与编码唯一性、因子名冲突、小区长宽与株行距几何一致性（容差 5%），并提示采样点伪重复风险。
- `splitplot design`：在完整区组内随机主区、在主区内随机副区；单一 Mersenne Twister 流由种子驱动，同种子可复现。
- 输出 `allocation.csv`（UTF-8 BOM，含小区行列端点）、`design.json`（schema 1.0，含随机化说明与 SHA-256 分配摘要）与 `field-map.png` / `field-map.svg`。
- 非空输出目录保护与 `--force`；`--formats` 选择图形格式；`--seed` 覆盖配置种子。
- `splitplot power`：按主区/残差两层误差的蒙特卡洛功效模拟，输出主区、副区、交互功效，主区低于 80% 时搜索建议区组数，可写 JSON。
- `splitplot model`：输出 statsmodels 与 R（`aov` / `lmer`）的误差分层公式、自由度与常见错误说明。
- `splitplot methods`：从已校验配置生成中英文方法段草稿。
- `tests/`：49 个 pytest 测试，覆盖 CLI 退出码、校验边界、随机化不变量、功效方向性与解析参照。
- GitHub Actions CI：Ubuntu 与 Windows × Python 3.11/3.12，执行 `ruff check .` 与 `pytest`。
- `docs/methods.md`、示例配置、MIT 许可证、CITATION.cff 与贡献指南。

### Known limitations

- 只支持两因子随机完全区组裂区设计，要求完整区组且无缺失小区。
- 不拟合数据，只给出模型公式；功效依赖已知 ICC 与正态独立同方差假设。
- 布局图为矩形示意，不含 GIS 坐标与机械转弯半径。
