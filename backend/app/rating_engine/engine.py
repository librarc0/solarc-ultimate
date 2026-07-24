"""
EaglesPower OpenSkill 评分引擎

算法策略：
  Level 0 — 纯 OpenSkill（无个人统计）
  Level 1 — OpenSkill + scores 参数（比分差影响涨跌幅）
  Level 2 — OpenSkill + 进球贡献加权
  Level 3 — OpenSkill + 进球 + 助攻 + 防守盘贡献加权
"""
from __future__ import annotations

from dataclasses import dataclass

from openskill.models import PlackettLuce


# OpenSkill 默认值（公开常量，供外部引用）
DEFAULT_MU: float = 25.0
DEFAULT_SIGMA: float = 8.333

# 战力分基准偏移：所有 conservative_rating = CONSERVATIVE_BASELINE + (mu - 3*sigma)
# 初始玩家 mu=25, sigma=8.333 → conservative = 50 + (25 - 25) = 50
# 保底 0 防止出现负分
CONSERVATIVE_BASELINE: float = 50.0


def conservative_score(mu: float, sigma: float) -> float:
    """计算保守战力分，最低为 0。"""
    return max(0.0, CONSERVATIVE_BASELINE + mu - 3.0 * sigma)


# ---------------------------------------------------------------------------
# 数据结构（纯 dataclass，不依赖 ORM）
# ---------------------------------------------------------------------------

@dataclass
class EngineSettings:
    """从 TeamSettings ORM 构建此对象后传入引擎，不读全局常量。"""
    # ── 个人贡献调整 ──
    alpha: float = 0.3              # 贡献差异映射到 weight 的放大系数
    beta: float = 0.6               # 进球贡献权重
    gamma: float = 0.4              # 助攻贡献权重
    defense_weight: float = 0.1     # 防守次数贡献权重（Level 3）
    weight_cap: float = 2.0         # OpenSkill weights 上限（≥1.0）
    # ── 综合评分混合 ──
    composite_ts_weight: float = 0.85
    composite_perf_weight: float = 0.15
    composite_attendance_weight: float = 0.0
    # ── deprecated（v1 遗留，不再参与计算）──
    winner_floor_factor: float = 0.1  # [deprecated] 改为 OpenSkill weights 原生处理
    sigma_bonus_factor: float = 0.15  # [deprecated] σ 由 OpenSkill tau 管理
    # ── 外战虚拟对手 ──
    external_opp_mu_min: float = 15.0   # 对手强度=1 时的虚拟 mu
    external_opp_mu_max: float = 50.0   # 对手强度=10 时的虚拟 mu
    external_opp_sigma: float = 6.0     # 虚拟对手固定 sigma
    external_impact_multiplier: float = 1.0  # 外战结果对评分的影响力倍率（相对内战）
    # ── OpenSkill 模型超参数（队伍级）──
    openskill_mu: float = DEFAULT_MU
    openskill_sigma: float = DEFAULT_SIGMA
    openskill_beta: float = DEFAULT_MU / 6.0
    openskill_tau: float = DEFAULT_MU / 300.0
    openskill_kappa: float = 0.0001
    openskill_margin: float = 0.0
    openskill_limit_sigma: bool = False
    openskill_balance: bool = True


@dataclass
class PlayerRatingInput:
    """Single player entering the rating calculation."""
    player_id: int
    mu: float
    sigma: float
    goals: int | None = None
    assists: int | None = None
    defenses: int | None = None  # 防守次数（下塞拦截次数）


@dataclass
class PlayerRatingOutput:
    """Rating result for one player."""
    player_id: int
    mu_before: float
    sigma_before: float
    mu_after: float
    sigma_after: float
    conservative_before: float
    conservative_after: float
    delta_mu: float


@dataclass
class MatchData:
    """All data needed to calculate match ratings."""
    team_a: list[PlayerRatingInput]
    team_b: list[PlayerRatingInput]
    team_a_score: int
    team_b_score: int
    data_level: int = 0             # 0-3


# ---------------------------------------------------------------------------
# 引擎实现
# ---------------------------------------------------------------------------

class RatingEngine:
    """
    OpenSkill PlackettLuce 评分引擎。
    每个实例绑定一套 TeamSettings，多次调用 calculate_* 方法线程安全。
    """

    def __init__(self, settings: EngineSettings | None = None):
        self.settings = settings or EngineSettings()
        self._model = PlackettLuce(
            mu=self.settings.openskill_mu,
            sigma=self.settings.openskill_sigma,
            beta=self.settings.openskill_beta,
            tau=self.settings.openskill_tau,
            kappa=self.settings.openskill_kappa,
            margin=self.settings.openskill_margin,
            limit_sigma=self.settings.openskill_limit_sigma,
            balance=self.settings.openskill_balance,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_internal(self, match: MatchData) -> list[PlayerRatingOutput]:
        """
        内战评分：两组参与者 A vs B。
        Level 0 → 返回空列表（不更新评分）。
        Level 1 → 纯 OpenSkill（比分作为 scores 参数）。
        Level 2/3 → OpenSkill + 原生 weights 个人贡献加权。
        """
        if match.data_level == 0:
            return []
        if not match.team_a or not match.team_b:
            return []

        ra = [self._model.rating(mu=p.mu, sigma=p.sigma) for p in match.team_a]
        rb = [self._model.rating(mu=p.mu, sigma=p.sigma) for p in match.team_b]

        if match.data_level >= 2:
            # v2: 用 OpenSkill 原生 weights 传递个人贡献
            wa = self._compute_weights(match.team_a, match.team_a_score)
            wb = self._compute_weights(match.team_b, match.team_b_score)
            new_ra, new_rb = self._model.rate(
                [ra, rb],
                scores=[match.team_a_score, match.team_b_score],
                weights=[wa, wb],
            )
        else:
            # Level 1: 纯 OpenSkill，无个人贡献
            new_ra, new_rb = self._model.rate(
                [ra, rb],
                scores=[match.team_a_score, match.team_b_score],
            )

        results: list[PlayerRatingOutput] = []
        for p, old, new in zip(match.team_a, ra, new_ra):
            results.append(self._make_output(p, old, new))
        for p, old, new in zip(match.team_b, rb, new_rb):
            results.append(self._make_output(p, old, new))

        return results

    def calculate_external(
        self,
        match: MatchData,
        opponent_strength: int,
        *,
        calibrated_mu: float | None = None,
        calibrated_sigma: float | None = None,
    ) -> list[PlayerRatingOutput]:
        """
        外战评分：本队 vs 虚拟对手（根据强度 1-10 构造或使用校准值）。
        只返回本队队员的评分结果。
        Level 0 → 返回空列表。

        calibrated_mu/sigma: 由联盟排行榜自适应校准提供时优先使用，
        否则回退到 opponent_strength 线性插值。
        """
        if match.data_level == 0:
            return []

        home_team = match.team_a  # 外战只录己方队伍
        if not home_team:
            return []
        team_score = match.team_a_score
        opp_score = match.team_b_score

        # 虚拟对手建模
        s = self.settings
        if calibrated_mu is not None:
            virtual_mu = calibrated_mu
            virtual_sigma = calibrated_sigma if calibrated_sigma is not None else s.external_opp_sigma
        else:
            mu_range = s.external_opp_mu_max - s.external_opp_mu_min
            virtual_mu = s.external_opp_mu_min + (opponent_strength - 1) * (mu_range / 9.0)
            virtual_sigma = s.external_opp_sigma
        n = len(home_team)

        ra = [self._model.rating(mu=p.mu, sigma=p.sigma) for p in home_team]
        virtual_team = [
            self._model.rating(mu=virtual_mu, sigma=virtual_sigma)
            for _ in range(n)
        ]

        if match.data_level >= 2:
            wa = self._compute_weights(home_team, team_score)
            wb = [1.0] * n  # 虚拟对手无个人贡献
            new_ra, _ = self._model.rate(
                [ra, virtual_team],
                scores=[team_score, opp_score],
                weights=[wa, wb],
            )
        else:
            new_ra, _ = self._model.rate(
                [ra, virtual_team],
                scores=[team_score, opp_score],
            )

        results = [
            self._make_output(p, old, new)
            for p, old, new in zip(home_team, ra, new_ra)
        ]

        # 外战影响力倍率：同时缩放 Δμ 和 Δσ
        m = s.external_impact_multiplier
        if m != 1.0:
            results = [
                PlayerRatingOutput(
                    player_id=r.player_id,
                    mu_before=r.mu_before,
                    sigma_before=r.sigma_before,
                    mu_after=r.mu_before + (r.mu_after - r.mu_before) * m,
                    sigma_after=r.sigma_before + (r.sigma_after - r.sigma_before) * m,
                    conservative_before=r.conservative_before,
                    conservative_after=conservative_score(
                        r.mu_before + (r.mu_after - r.mu_before) * m,
                        r.sigma_before + (r.sigma_after - r.sigma_before) * m,
                    ),
                    delta_mu=r.delta_mu * m,
                )
                for r in results
            ]
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_weights(
        self,
        players: list[PlayerRatingInput],
        team_score: int,
    ) -> list[float]:
        """
        计算 OpenSkill 原生 weights（v2 核心机制）。

        贡献分：
          contrib_i = beta*goals/team_score + gamma*assists/team_score
                    + defense_weight*max(0,pm)/team_score

        weight 映射（线性，以队均为锚点）：
          w_i = 1.0 + alpha * (contrib_i / mean_contrib - 1.0)
          clamp 到 [1.0, weight_cap]

        weight > 1 的球员在 OpenSkill 贝叶斯更新中获得更大 Δμ 和更快 σ 收敛。
        """
        s = self.settings
        denom = max(team_score, 1)

        contribs = []
        for p in players:
            g = (p.goals or 0) * s.beta / denom
            a = (p.assists or 0) * s.gamma / denom
            d = max(0, (p.defenses or 0)) * s.defense_weight / denom
            contribs.append(g + a + d)

        mean_contrib = sum(contribs) / max(len(contribs), 1)
        mean_contrib = max(mean_contrib, 1e-9)  # 防止除 0

        weights = []
        for contrib in contribs:
            ratio = contrib / mean_contrib
            w = 1.0 + s.alpha * (ratio - 1.0)
            w = max(1.0, min(s.weight_cap, w))
            weights.append(w)
        return weights

    def _make_output(self, p: PlayerRatingInput, old, new) -> PlayerRatingOutput:
        """Build PlayerRatingOutput from OpenSkill rate() results."""
        delta = new.mu - p.mu
        return PlayerRatingOutput(
            player_id=p.player_id,
            mu_before=p.mu,
            sigma_before=p.sigma,
            mu_after=new.mu,
            sigma_after=new.sigma,
            conservative_before=conservative_score(p.mu, p.sigma),
            conservative_after=conservative_score(new.mu, new.sigma),
            delta_mu=delta,
        )

