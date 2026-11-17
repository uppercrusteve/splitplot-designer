"""Monte Carlo power behaviour and model-strata text."""

from __future__ import annotations

import pytest
from scipy import stats

from splitplot_designer.models import build_model_summary, build_model_text
from splitplot_designer.power import normal_approximation, simulate_power


def test_more_blocks_increase_main_power(config) -> None:
    low = simulate_power(blocks=3, effect=0.6, icc=0.3, sims=120, seed=5, recommend=False)
    high = simulate_power(blocks=8, effect=0.6, icc=0.3, sims=120, seed=5, recommend=False)
    assert high.power_main > low.power_main


def test_higher_icc_lowers_main_power(config) -> None:
    easy = simulate_power(blocks=6, effect=0.8, icc=0.05, sims=120, seed=9, recommend=False)
    hard = simulate_power(blocks=6, effect=0.8, icc=0.8, sims=120, seed=9, recommend=False)
    assert easy.power_main > hard.power_main


def test_zero_effect_gives_low_power() -> None:
    result = simulate_power(blocks=4, effect=0.0, icc=0.3, sims=100, seed=3, recommend=False)
    assert result.power_main < 0.25
    assert result.power_sub < 0.25


def test_power_is_a_proportion_and_reproducible() -> None:
    first = simulate_power(blocks=5, effect=0.7, icc=0.3, sims=80, seed=11, recommend=False)
    second = simulate_power(blocks=5, effect=0.7, icc=0.3, sims=80, seed=11, recommend=False)
    assert first.power_main == second.power_main
    assert 0.0 <= first.power_main <= 1.0
    assert 0.0 <= first.power_interaction <= 1.0


def test_error_df_matches_split_plot_formula() -> None:
    result = simulate_power(blocks=4, effect=0.5, icc=0.3, sims=10, seed=1, recommend=False)
    assert result.error_df == 4 * 2 * 3 - (4 * 2 + 2 + 2)


def test_recommendation_is_none_when_power_already_high() -> None:
    result = simulate_power(blocks=10, effect=1.4, icc=0.05, sims=60, seed=2)
    assert result.power_main >= 0.8
    assert result.recommended_blocks is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"blocks": 1, "effect": 0.5, "icc": 0.2}, "blocks"),
        ({"blocks": 4, "effect": 4.0, "icc": 0.2}, "effect"),
        ({"blocks": 4, "effect": 0.5, "icc": 1.0}, "icc"),
        ({"blocks": 4, "effect": 0.5, "icc": 0.2, "alpha": 0.0}, "alpha"),
        ({"blocks": 4, "effect": 0.5, "icc": 0.2, "sims": 5}, "sims"),
    ],
)
def test_invalid_arguments_raise(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        simulate_power(**kwargs)


def test_main_power_matches_noncentral_f_reference() -> None:
    """Main power must follow the whole-plot stratum, not a reference-block contrast."""

    result = simulate_power(blocks=8, effect=0.8, icc=0.3, sims=1000, seed=1, recommend=False)
    ss_main = 8 * 3 * 2 * 0.8**2
    noncentrality = ss_main / (0.3 * 3 + 0.7)
    analytic = stats.ncf.sf(stats.f.ppf(0.95, 1, 7), 1, 7, noncentrality)
    assert abs(result.power_main - analytic) < 0.08


def test_normal_approximation_is_bounded() -> None:
    value = normal_approximation(blocks=4, effect=0.5, icc=0.3)
    assert 0.0 <= value <= 1.0


def test_model_text_names_the_whole_plot_stratum(config) -> None:
    text = build_model_text(config)
    assert "block:main" in text
    assert "实验单元" in text or "experimental unit" in text
    assert "pseudo" in text.lower() or "伪重复" in text
    assert "Error(4/floor)" in text
    assert "df = 12" in text
    assert "df = 3" in text


def test_model_summary_degrees_of_freedom(config) -> None:
    summary = build_model_summary(config)
    assert summary["statistical_unit"] == "plot"
    assert summary["main_df"] == 2 - 1
    assert summary["block_main_df"] == (4 - 1) * (2 - 1)
    assert summary["interaction_df"] == (2 - 1) * (3 - 1)
    assert summary["residual_df"] == 2 * (4 - 1) * (3 - 1)
    assert summary["sub_plot_error"] == "residual"
    assert len(summary["warnings"]) == 2
