# 贡献指南 / Contributing

## 环境

需要 Python 3.10+。开发安装：

```bash
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
```

提交前必须通过：

```bash
ruff check .
pytest -q
```

CI 在 Ubuntu 与 Windows、Python 3.11/3.12 上执行同样两项；任一失败不合并。

## 代码约定

- `src/` 布局；公共函数带类型标注；面向用户的错误用 `ConfigError` / `OutputError`，由 CLI 统一渲染成 `文件:行号` 形式并以非零码退出。
- 用户可见文案中英双语；代码注释与命名用英文。
- 新的统计行为必须同时更新 `docs/methods.md`（含公式与出处）、README 的对应说明与 `tests/`。不许只改实现不改文档。
- 随机化只能通过显式种子驱动，禁止依赖未固定的全局随机状态；改动分配逻辑会改变历史摘要，须在 `CHANGELOG.md` 说明。
- 保持依赖精简；不引入 Web 框架或绘图之外的运行时。

## 测试要求

- 主路径、边界值、错误输入三类都要有测试；断言具体值、行号、退出码或产物大小，不写“只断言不报错”。
- 涉及随机性的测试固定种子；同时断言同种子可复现、异种子会变化。
- 统计检验的改动应附带解析解或已知性质的回归测试（例如功效随区组数上升、随 ICC 下降）。
- 临时文件写到 `tmp_path`，不要污染仓库。

## 数据口径

- `examples/` 必须标注属于“实测 / 公开数据 / 合成演示”；当前两份示例都是合成演示，水平名称只是场景化标签。
- 合成配置可以虚构，但几何必须自洽：小区长 = 每行株数 × 株距，小区宽 = 行数 × 行距（容差 5%）。
- 引入实测数据需说明地点、年份、品种、单位与采集方式；涉及第三方数据要确认许可并在 README 记录来源。
- 不要提交真实试验的未发表原始数据，除非作者同意。

## Issue 与 Pull Request

- Issue 请写清：`splitplot --version`、操作系统与 Python 版本、最小复现 YAML、实际输出与期望输出。
- PR 保持单一主题，说明动机与用户可见变化，附测试结果；新增字段或校验规则要同步 README 的输入表。
- 提交信息用 `feat:` / `fix:` / `test:` / `docs:` / `chore:` 前缀，正文写“为什么”。
- 默认分支为 `main`。

## 许可证

贡献即同意以 MIT 许可证发布。
