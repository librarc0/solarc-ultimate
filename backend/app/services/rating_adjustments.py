"""Pure adjustment helpers for rating apply flow."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.match import TeamSettings


@dataclass(frozen=True)
class AdjustmentCoefficients:
    turnover_penalty: float
    turnover_sigma_factor: float
    turnover_threshold: int
    turnover_multiplier: float
    dline_bonus_per: float
    universe_bonus_per: float


def resolve_adjustment_coefficients(ts: TeamSettings | None) -> AdjustmentCoefficients:
    return AdjustmentCoefficients(
        turnover_penalty=ts.turnover_penalty if ts else 0.2,
        turnover_sigma_factor=ts.turnover_sigma_factor if ts else 0.3,
        turnover_threshold=ts.consecutive_turnover_threshold if ts else 3,
        turnover_multiplier=ts.consecutive_turnover_multiplier if ts else 1.5,
        dline_bonus_per=ts.block_mu_bonus if ts else 0.05,
        universe_bonus_per=ts.universal_point_bonus if ts else 0.5,
    )


def compute_turnover_penalty(
    turnover_count: int,
    coefficients: AdjustmentCoefficients,
) -> float:
    """v2: turnover 仅惩罚 μ，不再膨胀 σ（σ 由 OpenSkill tau 统一管理）。"""
    if turnover_count <= coefficients.turnover_threshold:
        mu_penalty = turnover_count * coefficients.turnover_penalty
    else:
        mu_penalty = (
            coefficients.turnover_threshold * coefficients.turnover_penalty
            + (turnover_count - coefficients.turnover_threshold)
            * coefficients.turnover_penalty
            * coefficients.turnover_multiplier
        )
    return mu_penalty


def compute_total_bonus(
    player_id: int,
    universe_point_players: set[int],
    dline_event_count: dict[int, int],
    coefficients: AdjustmentCoefficients,
) -> float:
    universe_bonus = coefficients.universe_bonus_per if player_id in universe_point_players else 0.0
    dline_bonus = dline_event_count.get(player_id, 0) * coefficients.dline_bonus_per
    return universe_bonus + dline_bonus
