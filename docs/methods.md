# 方法说明 / Methods

本文件记录 `splitplot-designer` 使用的统计模型、误差分层、随机化算法、功效模拟假设、单位、出处与局限。所有公式与实现一一对应；模型公式是供外部软件使用的草稿，本工具本身不拟合数据。

## 1. 适用范围与统计单元

只支持一个设计族：随机完全区组裂区设计（randomized complete block split-plot）。恰好两个处理因子——主区因子 A（`main_plot`）与副区因子 B（`sub_plot`）——分别有 `a` 与 `s` 个水平（均 `>= 2`），完整区组数 `r >= 3`，每个区组包含全部 `a × s` 个组合且无缺失小区。

统计单元始终是**小区（whole plot）**。每小区的多个采样点是子样本（subsamples），不是重复；分析前应按 `plot_id` 求均值，或在小区的随机效应内建模。单株同样只是技术重复。

## 2. 设计结构与模型

记区组 `i = 1..r`、主区水平 `j = 1..a`、副区水平 `k = 1..s`，观测值 `y_ijk`：

$$
y_{ijk} = \mu + \beta_i + \tau_j + \gamma_k + (\tau\gamma)_{jk} + u_{ij} + \varepsilon_{ijk}
$$

约束：`Σ_j τ_j = 0`、`Σ_k γ_k = 0`、`Σ_j (τγ)_jk = 0`、`Σ_k (τγ)_jk = 0`。

- `β_i`：区组效应。检验时按随机效应处理（等价于 `block` 与 `block × main` 两个误差层）。
- `τ_j`：主区（whole-plot）处理效应，固定。
- `γ_k`：副区（sub-plot）处理效应，固定。
- `(τγ)_jk`：主区 × 副区交互，固定。
- `u_ij ~ N(0, σ²_w)`：主区误差，每个 `block × main` 单元抽一次，独立。
- `ε_ijk ~ N(0, σ²_p)`：小区内残差，每个小区一次，独立于 `u_ij`。

总误差方差 `σ² = σ²_w + σ²_p`。ICC 定义为 `ρ = σ²_w / σ²`，取值 `[0, 1)`。

对应的 statsmodels 写法（`plot_means` 是已按小区聚合的数据，含 `block` 与 `y` 列，处理列沿用因子名）：

```python
full = ols(
    "y ~ C(block) + C(main) + C(block):C(main) + C(sub) + C(main):C(sub)",
    data=plot_means,
).fit()
```

R 写法：

```r
aov(y ~ main * sub + Error(block / main), data = plot_means)
lmer(y ~ main * sub + (1 | block) + (1 | block:main), data = plot_means)
```

## 3. 误差分层与检验

方差分析表（自由度）：

| 来源 | df |
| --- | --- |
| 区组 block | `r - 1` |
| 主区 main | `a - 1` |
| 主区误差 block:main | `(r - 1)(a - 1)` |
| 副区 sub | `s - 1` |
| 主区 × 副区 | `(a - 1)(s - 1)` |
| 残差 residual | `a(r - 1)(s - 1)` |

检验统计量：

$$
F_{\text{main}} = \frac{MS_{\text{main}}}{MS_{\text{block:main}}}
\sim F\bigl(a-1,\ (r-1)(a-1)\bigr)
$$

$$
F_{\text{sub}} = \frac{MS_{\text{sub}}}{MS_{\text{residual}}}
\sim F\bigl(s-1,\ a(r-1)(s-1)\bigr), \qquad
F_{\text{int}} = \frac{MS_{\text{int}}}{MS_{\text{residual}}}
\sim F\bigl((a-1)(s-1),\ a(r-1)(s-1)\bigr)
$$

期望均方（在零效应下给出分母的构成）：

$$
E(MS_{\text{block:main}}) = \sigma_p^2 + s\,\sigma_w^2,\qquad
E(MS_{\text{residual}}) = \sigma_p^2
$$

主区效应若改用残差作分母，`σ²_w` 被漏掉，F 值膨胀、p 值偏乐观。只含 `(1 | block)` 的混合模型同样错误：主区处理仍缺 `block:main` 随机截距。

**实现细节（功效模拟）**：由于 `block × main` 单元均值在参数化中已饱和，直接从一个含 `block:main` 的模型里删除 `main` 只检验参照区组的对比，会低估主区功效。实现改为在单元均值模型上按 `block → block + main → block + main + block:main` 的顺序计算经典附加平方和，再以 `MS_block:main` 为分母。副区与交互仍用全模型删除对应列得到的附加平方和除以残差均方。

## 4. 随机化算法

1. 以配置的 `seed`（`0..4294967295`）创建单一 `random.Random` 流（Mersenne Twister）。
2. 对每个区组 `1..r`：先 `shuffle` 主区水平列表。
3. 对洗牌后的每个主区位置：独立 `shuffle` 副区水平列表。
4. 位置确定性映射到坐标：每小区占 `vines_per_row` 株宽；`vine_start = ((main_pos-1)·s + (sub_pos-1))·vines_per_row + 1`；区组占 `rows_per_plot` 行带，相邻区组间插入 `buffer_rows` 行缓冲。行号与株号均从 1 开始、含端点。
5. 小区 ID 形如 `B03-M02-S01`（区组/主区位置/副区位置）。
6. 对 `allocation.csv` 的逗号连接行取 SHA-256 作为分配摘要。

每个区组是主区的完整排列，每个主区内是副区的完整排列，因此结构平衡、无重复。种子固定时分配与摘要完全一致；换种子则改变分配。摘要是归档指纹，不防篡改签名。

## 5. 几何与校验

几何以米为单位：小区长（沿行向）应等于 `vines_per_row × vine_spacing_m`，小区宽（跨行向）应等于 `rows_per_plot × row_spacing_m`。校验容差为 `max(5%, 0.05 m)`，超出报错。`rows_per_plot`、`vines_per_row`、`buffer_rows` 均须 `>= 1`。

其他硬性校验：区组 `>= 3`；种子在 32 位无符号范围；因子名不同且非空；每因子至少 2 个水平；编码字母开头、仅 ASCII 字母数字下划线连字符、最长 12 字符、因子内唯一；`treated_as ∈ {plot_mean, replicates}`；`points_per_plot >= 1`。错误带源文件行号，退出码 1。

面积按矩形计算：`plot_area_m2 = plot_length_m × plot_width_m`，仅用于方案描述，不代表可种植面积修正。

## 6. 功效模拟

数据生成过程与第 2 节模型一致，另加固定区组效应。总误差 SD 固定为 1，故效应量可直接解释为 Cohen's f：

- 主效应向量等距取值、中心化，并缩放到 `Σ_j τ_j² = a·f²`（即真实 `f = sqrt(Στ²/a)`）。
- 副效应同理，`Σ_k γ_k² = s·f²`。
- 交互矩阵取主、副效应外积后中心化缩放，使其 `f = effect`（`ΣΣ(τγ)² = a·s·f²`）。
- 区组效应为等距固定向量，缩放到 `f = 0.35`。

每次模拟：`u_ij ~ N(0, ρ)`、`ε_ijk ~ N(0, 1-ρ)`，计算第 3 节三个 F 值，由 F 尾概率得到双侧 p 值，记录是否 `< alpha`。功效是 `sims` 次重复中的拒绝比例。主效应功效低于 0.80 且区组数 `< 12` 时，依次尝试 `r+1 .. min(12, r+6)`，每档最多 `min(sims, 300)` 次，报告首个达到 0.80 的区组数。

主效应非中心参数（`Στ² = a f²`）：

$$
\lambda_{\text{main}} = \frac{r s \sum_j \tau_j^2}{\sigma_p^2 + s\sigma_w^2}
= \frac{r s a f^2}{(1-\rho) + s\rho}
$$

副区与交互以 `σ_p² = 1-ρ` 为分母，非中心参数分别为 `r a s f²/(1-ρ)` 与 `r a s f²/(1-ρ)`（交互的平方和按其自身 `f` 标度）。默认 `sims = 500`，二项抽样下 `p = 0.5` 时单次运行的标准误约 `2.2` 个百分点，比较不同设计时应固定种子并增大 `sims`。

`normal_approximation()` 另给出主效应的粗略解析核对（`sqrt(2ρ/(r·a))/f` 的正态近似），只用于交叉检查，不作为报告值。

## 7. 单位与符号

| 量 | 单位 / 取值 |
| --- | --- |
| 行号、株号、行数、株数 | 整数，1 起，含端点 |
| 株距、行距、小区长宽、缓冲行宽 | m |
| 小区面积 | m² |
| 自由度 df | 无量纲整数 |
| Cohen's f | 无量纲（总误差 SD = 1） |
| ICC `ρ` | `[0, 1)` 的比例 |
| `alpha` | `(0, 1)` 的概率 |
| `seed` | 无符号 32 位整数 |

## 8. 文献

- Gomez, K. A., & Gomez, A. A. (1984). *Statistical Procedures for Agricultural Research* (2nd ed.). Wiley. 裂区设计的布局、误差分层与方差分析表。
- Casler, M. D. (2015). Fundamentals of Experimental Design: Guidelines for Designing Successful Experiments. *Agronomy Journal*, 107(2), 692–705. https://doi.org/10.2134/agronj2013.0114 区组、重复与功效设计原则。
- Piepho, H.-P., Büchse, A., & Emrich, K. (2003). A Hitchhiker's Guide to Mixed Models for Randomized Experiments. *Journal of Agronomy and Crop Science*, 189(5), 310–322. https://doi.org/10.1046/j.1439-037X.2003.00049.x 随机化试验的混合模型与误差层。
- Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences* (2nd ed.). Lawrence Erlbaum. Cohen's f 的定义。
- Bates, D., Mächler, M., Bolker, B., & Walker, S. (2015). Fitting Linear Mixed-Effects Models Using lme4. *Journal of Statistical Software*, 67(1), 1–48. https://doi.org/10.18637/jss.v067.i01 `lmer` 实现。

## 9. 局限

- 单一设计族：两因子、完整区组、无缺失小区；不支持裂-裂区、条区、拉丁方、增广设计或不平衡重复。
- `model` 与 `methods` 只生成文本，不读取数据、不拟合、不做多重比较或残差诊断。
- 功效依赖已知且固定的 ICC、正态独立同方差误差、无离群值；区组效应在模拟中是固定向量而非每次重抽。
- 区组搜索是启发式上限（最多 12 个区组、每次最多前进 6），不是严格优化；模拟功效不是某次试验的事后保证。
- 缓冲行只加在相邻区组之间；同一区组内小区沿行向紧邻，没有额外空隙。布局是矩形示意图，无 GIS 坐标、坡向、道路或机械转弯半径。
- 摘要基于 CSV 文本，换行符或格式变化会改变摘要；它不具签名性质。
- 中文图注依赖系统 CJK 字体（微软雅黑、黑体、Noto Sans CJK SC 等），缺失时回落到 DejaVu Sans，中文可能显示为方框。
- 只输出 PNG/SVG；默认 150 dpi，未针对印刷尺寸做校准。
