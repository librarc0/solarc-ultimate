"""Unit tests for pure rating adjustment helpers."""

import pytest

from app.models.match import TeamSettings
from app.services.rating_adjustments import (
    compute_total_bonus,
    compute_turnover_penalty,
    resolve_adjustment_coefficients,
)


def test_resolve_adjustment_coefficients_defaults():
    c = resolve_adjustment_coefficients(None)
    assert c.turnover_penalty == pytest.approx(0.2)
    assert c.turnover_sigma_factor == pytest.approx(0.3)
    assert c.turnover_threshold == 3
    assert c.turnover_multiplier == pytest.approx(1.5)
    assert c.dline_bonus_per == pytest.approx(0.05)
    assert c.universe_bonus_per == pytest.approx(0.5)


def test_resolve_adjustment_coefficients_from_team_settings():
    ts = TeamSettings(
        team_id=1,
        updated_by=1,
        turnover_penalty=0.4,
        turnover_sigma_factor=0.8,
        consecutive_turnover_threshold=2,
        consecutive_turnover_multiplier=1.25,
        block_mu_bonus=0.09,
        universal_point_bonus=0.7,
    )
    c = resolve_adjustment_coefficients(ts)
    assert c.turnover_penalty == pytest.approx(0.4)
    assert c.turnover_sigma_factor == pytest.approx(0.8)
    assert c.turnover_threshold == 2
    assert c.turnover_multiplier == pytest.approx(1.25)
    assert c.dline_bonus_per == pytest.approx(0.09)
    assert c.universe_bonus_per == pytest.approx(0.7)


def test_compute_turnover_penalty_linear_zone():
    c = resolve_adjustment_coefficients(None)
    mu_penalty = compute_turnover_penalty(2, c)
    assert mu_penalty == pytest.approx(0.4)


def test_compute_turnover_penalty_over_threshold():
    c = resolve_adjustment_coefficients(None)
    mu_penalty = compute_turnover_penalty(5, c)
    # threshold=3 => 3*0.2 + 2*0.2*1.5 = 1.2
    assert mu_penalty == pytest.approx(1.2)


def test_compute_total_bonus_with_universe_and_dline():
    c = resolve_adjustment_coefficients(None)
    bonus = compute_total_bonus(
        player_id=10,
        universe_point_players={10},
        dline_event_count={10: 2},
        coefficients=c,
    )
    assert bonus == pytest.approx(0.6)
