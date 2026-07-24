"""Rating settings mapping helpers."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import TeamSettings
from app.models.player import Player, PlayerStatus
from app.rating_engine.engine import EngineSettings


def build_engine_settings(ts: TeamSettings | None) -> EngineSettings:
    if ts is None:
        return EngineSettings()
    return EngineSettings(
        alpha=ts.alpha,
        beta=ts.beta,
        gamma=ts.gamma,
        defense_weight=ts.defense_weight,
        weight_cap=getattr(ts, 'weight_cap', 2.0),
        composite_ts_weight=ts.composite_ts_weight,
        composite_perf_weight=ts.composite_perf_weight,
        composite_attendance_weight=ts.composite_attendance_weight,
        winner_floor_factor=ts.winner_floor_factor,
        sigma_bonus_factor=ts.sigma_bonus_factor,
        external_opp_mu_min=ts.external_opp_mu_min,
        external_opp_mu_max=ts.external_opp_mu_max,
        external_opp_sigma=ts.external_opp_sigma,
        external_impact_multiplier=ts.external_impact_multiplier,
        openskill_mu=ts.openskill_mu,
        openskill_sigma=ts.openskill_sigma,
        openskill_beta=ts.openskill_beta,
        openskill_tau=ts.openskill_tau,
        openskill_kappa=ts.openskill_kappa,
        openskill_margin=ts.openskill_margin,
        openskill_limit_sigma=ts.openskill_limit_sigma,
        openskill_balance=ts.openskill_balance,
    )


async def get_suggested_mu(db: AsyncSession, team_id: int) -> float:
    """T039 [US4]: 计算队伍的建议初始 μ（用于审核新队员时参考）。

    规则（FR-013）：
    - 取该队 active 且非 guest（is_guest=False）player 的 μ 算术平均值
    - 若有效样本少于 3 人，回退为该队 TeamSettings.openskill_mu（默认 25.0）
    """
    # 获取 active 非 guest 成员的 mu 值
    result = await db.execute(
        select(Player.mu).where(
            Player.team_id == team_id,
            Player.status == PlayerStatus.active,
            Player.is_guest.is_(False),
        )
    )
    mu_values = [row[0] for row in result.all()]

    if len(mu_values) >= 3:
        return sum(mu_values) / len(mu_values)

    # 样本不足 3 人：回退到队伍的 OpenSkill 默认初始 μ
    ts_result = await db.execute(
        select(TeamSettings).where(TeamSettings.team_id == team_id)
    )
    ts = ts_result.scalar_one_or_none()
    return ts.openskill_mu if ts else 25.0
    if ts is None:
        return EngineSettings()
    return EngineSettings(
        alpha=ts.alpha,
        beta=ts.beta,
        gamma=ts.gamma,
        defense_weight=ts.defense_weight,
        weight_cap=getattr(ts, 'weight_cap', 2.0),
        composite_ts_weight=ts.composite_ts_weight,
        composite_perf_weight=ts.composite_perf_weight,
        composite_attendance_weight=ts.composite_attendance_weight,
        winner_floor_factor=ts.winner_floor_factor,
        sigma_bonus_factor=ts.sigma_bonus_factor,
        external_opp_mu_min=ts.external_opp_mu_min,
        external_opp_mu_max=ts.external_opp_mu_max,
        external_opp_sigma=ts.external_opp_sigma,
        external_impact_multiplier=ts.external_impact_multiplier,
        openskill_mu=ts.openskill_mu,
        openskill_sigma=ts.openskill_sigma,
        openskill_beta=ts.openskill_beta,
        openskill_tau=ts.openskill_tau,
        openskill_kappa=ts.openskill_kappa,
        openskill_margin=ts.openskill_margin,
        openskill_limit_sigma=ts.openskill_limit_sigma,
        openskill_balance=ts.openskill_balance,
    )
