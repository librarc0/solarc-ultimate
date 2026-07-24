# OpenSkill 算法技术方案

> EaglesPower 评分引擎设计参考文档  
> 面向希望理解算法原理和实现决策的开发者

---

## 1. OpenSkill 是什么？

OpenSkill 是 TrueSkill（微软 Xbox 系统）的开源替代实现，基于 **Weng-Lin 2011 论文**（*A Bayesian Approximation Method for Online Ranking*）。

核心思想：**用概率分布表示"不确定的技能值"**。

每个队员不是一个固定数字，而是一个**正态分布**：

$$\text{skill} \sim \mathcal{N}(\mu, \sigma^2)$$

| 参数 | 含义 | 初始值 |
|------|------|--------|
| $\mu$ (mu) | 技能均值——你"最可能"的真实水平 | 25.0 |
| $\sigma$ (sigma) | 不确定性——系统对你了解多少 | 8.333 |

**关键规律**：
- 新队员 σ 很大（系统还不了解你），μ 波动快
- 参赛越多，σ 越小（越来越"看准"你），μ 越稳定
- 保守估计 `conservative_rating = μ - 3σ`，表示"至少有这么强"

---

## 2. 三种模型的区别

`openskill` 库提供多个模型，本质是不同的"概率推断近似方法"：

### 2.1 PlackettLuce（推荐选型 ✅）

**原理**：把每支队伍视为一个整体进行排名，支持任意数量的队伍同时参与。  
计算每支队伍"赢得本场排名第一"的概率，然后用贝叶斯更新每个人的 μ/σ。

```
场景：A队(3人) vs B队(4人)，A队赢
输入：[[μ_a1, μ_a2, μ_a3], [μ_b1, μ_b2, μ_b3, μ_b4]]
排名：[1, 2]（A队第1，B队第2）
输出：每个人新的 (μ, σ)
```

**特点**：
- ✅ 天然支持多队同场（3队、4队 round-robin 都行）
- ✅ 支持不等人数队伍（3v5 完全没问题）
- ✅ 支持部分排名（并列名次）
- ✅ 计算速度快（线性近似）
- ⚠️ 把队伍成员技能直接加总作为队伍实力（隐含假设：实力可叠加）

**适合飞盘的原因**：飞盘是真正的团队竞技，且内战经常出现 5v6、4v7 的不等分阵容，PlackettLuce 对此处理最自然。

---

### 2.2 ThurstoneMostellerFull

**原理**：基于 Thurstone-Mosteller 配对比较模型，将每场比赛分解为所有可能的一对一配对，积分推断技能差异。

```
场景：A队 vs B队
等效为：A队每个人 vs B队每个人的 n×m 次配对比较
从所有配对结果推断个人技能
```

**特点**：
- ✅ 对个人技能差异更敏感（更擅长区分"队里的强弱"）
- ✅ 适合个人竞技（乒乓球、国际象棋积分）
- ❌ 不支持超过 2 支队伍同场（对多队比赛需要拆分）
- ❌ 对不等人数队伍处理有假设偏差
- ❌ 计算复杂度 O(n×m)，数学上更"重"

**不适合飞盘的原因**：飞盘是团队运动，队员表现高度依赖队友配合，"每个人都和对方所有人单独比"的假设与实际不符；另外无法处理外战（只有一支队伍）。

---

### 2.3 BradleyTerryFull

**原理**：Bradley-Terry 模型的完整（Full）版本，是 Thurstone-Mosteller 的简化变体。

**特点**：
- ✅ 数学形式最简单，可解释性强
- ❌ 同 ThurstoneMostellerFull，仅两两比较
- ❌ 不支持平局（平局需要特殊处理）
- ⚠️ Full 版本（完整贝叶斯更新）计算量比 Part 版本大，收敛较慢

**结论**：BradleyTerryFull 介于"理论上好看"和"工程上不实用"之间，在飞盘场景中无明显优势。

---

### 2.4 模型选型总结

| 特性 | PlackettLuce ✅ | ThurstoneMostellerFull | BradleyTerryFull |
|------|---------------|----------------------|-----------------|
| 支持 2+ 队伍 | ✅ | ❌ 仅2队 | ❌ 仅2队 |
| 不等人数队伍 | ✅ | ⚠️ 假设偏差 | ⚠️ 假设偏差 |
| 外战虚拟对手 | ✅ | ✅ | ✅ |
| 个人技能区分度 | 中等 | 高 | 中等 |
| 计算速度 | 快 | 较慢 | 中等 |
| 平局支持 | ✅（scores参数） | ✅ | ⚠️ 需特殊处理 |
| **飞盘适配度** | **⭐⭐⭐** | ⭐⭐ | ⭐ |

---

## 3. 数据与算法的结合方案

### 3.1 四个数据等级的处理策略

飞盘比赛的数据完整性差异很大（手动录入 vs 事后补录），必须支持降级处理：

```
Level 0: 只知道谁赢了
Level 1: 知道最终比分 (7:5)  
Level 2: 比分 + 部分个人统计
Level 3: 比分 + 全员进球/助攻/防守盘
```

#### Level 0 — 纯 OpenSkill 更新

```python
# 只有胜负，用原始 PlackettLuce
teams = [[μ_a1, μ_a2, μ_a3], [μ_b1, μ_b2, μ_b3]]
ranks = [1, 2]  # A队赢
new_ratings = model.rate(teams, ranks=ranks)
# 同队所有人获得相同幅度的 μ 变化
```

**效果**：胜队涨分，败队跌分，涨跌幅度由双方 μ 差距决定（强打弱赢了涨少，弱打强赢了涨多）。

---

#### Level 1 — 加入比分差权重

```python
# 比分 7:5，分差=2，引入 score margin 权重
score_margin = abs(score_a - score_b)  # = 2
# 用 scores 参数传入（PlackettLuce 支持 scores 参数表示资源分）
teams = [[μ_a1, μ_a2], [μ_b1, μ_b2]]
scores = [7, 5]  # 高分→排名靠前
new_ratings = model.rate(teams, scores=scores)
```

**效果**：7:1 惨败跌更多，7:6 险败跌较少——比纯胜负更合理。

> ⚠️ 注意：`openskill` 的 `scores` 参数是"越高越好"的资源分，直接传进球数即可。

---

#### Level 2 — 部分个人贡献加权

```python
# A队中，player1 有数据(3进球2助攻)，player2 无数据
# 策略：有数据的用贡献调整，无数据的用纯团队平均值

for player in match_players:
    if player.has_stats:
        contrib = beta * player.goals + gamma * player.assists
        contrib_normalized = contrib / team_avg_contrib  # 归一化
        # 在 OpenSkill 基础变化上叠加个人贡献偏移
        delta_mu += alpha * (contrib_normalized - 1.0) * base_delta_mu
```

---

#### Level 3 — 完整个人贡献加权（核心算法）

这是本系统区别于纯 TrueSkill 的最大设计亮点：

```python
def _apply_contribution_weighting(
    base_results: list[RatingResult],       # OpenSkill 基础计算结果
    match_players: list[MatchPlayerData],   # 个人统计数据
    settings: TeamSettings,                 # 管理员配置系数
) -> list[RatingResult]:
    """
    在 OpenSkill 基础变化上叠加个人贡献权重。
    
    设计原则：
    1. 不改变"谁赢谁输"的基本方向（贡献差只影响幅度，不反转符号）
    2. 贡献分在队内归一化（防止高进球场次对低贡献者过度惩罚）
    3. 系数 alpha 控制个人贡献对总变化量的影响比例
    """
    for team_players in [team_a, team_b]:
        # 1. 计算每人贡献分
        contribs = [
            settings.beta * p.goals 
            + settings.gamma * p.assists 
            + settings.d_disc_weight * max(0, p.plus_minus)
            for p in team_players
        ]
        
        # 2. 队内归一化（避免绝对值引起的偏差）
        mean_contrib = sum(contribs) / len(contribs) or 1.0
        normalized = [c / mean_contrib for c in contribs]
        
        # 3. 在基础 delta_mu 上做比例调整
        for player, norm in zip(team_players, normalized):
            base_delta = player.mu_after_base - player.mu_before
            # alpha 控制偏移幅度：alpha=0 → 完全不用个人贡献
            #                      alpha=1 → 贡献差异影响等同于团队基础变化
            adjustment = settings.alpha * (norm - 1.0) * abs(base_delta)
            player.mu_after = player.mu_before + base_delta + adjustment
    
    return adjusted_results
```

**数值示例**（alpha=0.3, beta=0.6, gamma=0.4）：

```
场景：A队 3:1 赢B队，base_delta_mu = +1.5 （OpenSkill基础涨分）

A队三人个人统计：
  player1: 2进球1助攻 → contrib = 0.6×2 + 0.4×1 = 1.6
  player2: 1进球0助攻 → contrib = 0.6×1 + 0.4×0 = 0.6
  player3: 0进球0助攻 → contrib = 0.0

队内归一化（均值 = 0.733）：
  player1: 1.6/0.733 = 2.18
  player2: 0.6/0.733 = 0.82
  player3: 0.0/0.733 = 0.0

最终 mu 调整：
  player1: +1.5 + 0.3×(2.18-1.0)×1.5 = +1.5 + 0.53 = +2.03 ✅ 涨最多
  player2: +1.5 + 0.3×(0.82-1.0)×1.5 = +1.5 - 0.08 = +1.42 ✅ 正常涨
  player3: +1.5 + 0.3×(0.00-1.0)×1.5 = +1.5 - 0.45 = +1.05 ✅ 涨最少（仍为正）
```

---

### 3.2 外战虚拟对手建模

外战没有对方队员数据，需要构造一个"虚拟对手队伍"参与 PlackettLuce 计算：

```python
def build_virtual_opponent(strength: int) -> list[Rating]:
    """
    将对手强度（1-10）映射为虚拟对手的 OpenSkill Rating 列表。
    
    映射公式：virtual_mu = 15 + (strength - 1) × (35 / 9)
    强度1 → μ=15.0（弱队），强度10 → μ=50.0（顶级强队）
    虚拟 σ 固定为 6.0（表示"我们对对手了解程度中等"）
    虚拟队员人数等于本队人数（保持对称性）
    """
    virtual_mu = 15.0 + (strength - 1) * (35.0 / 9.0)
    virtual_sigma = 6.0
    return [Rating(mu=virtual_mu, sigma=virtual_sigma)] * len(home_team)
```

**强度-μ 对照表**：

| 对手强度 | 虚拟 μ | 等效含义 |
|---------|--------|---------|
| 1 | 15.0 | 初学者/业余弱队 |
| 3 | 22.8 | 普通业余队 |
| 5 | 35.6 | 中等竞技水平 |
| 7 | 42.2 | 强队 |
| 9 | 48.9 | 精英队 |
| 10 | 50.0 | 顶级对手 |

> 参考：新队员初始 μ=25，保守估计 μ-3σ = 0；虚拟对手 μ=50 相当于"经验丰富的顶级飞盘选手水平"，给赢他们的本队成员足够高的奖励。

---

## 4. 可输出的技术参数

每场比赛计算完成后，以下参数均可从 OpenSkill + 记录数据中导出：

### 4.1 个人维度

| 参数 | 计算方式 | 含义 | 用途 |
|------|---------|------|------|
| `mu` (μ) | OpenSkill 原生输出 | 技能均值，越高越强 | 排行榜、雷达图 |
| `sigma` (σ) | OpenSkill 原生输出 | 不确定性，越低越稳定 | 评分置信度显示 |
| `conservative_rating` | μ - 3σ | 保守估计下限（99.7%概率超过此值） | **主排行榜排名依据** |
| `delta_mu` | μ_after - μ_before | 本场比赛的评分变化 | 赛后"你涨/跌了多少分" |
| `win_probability` | 见下方公式 | 与队内平均水平相比的预期胜率 | 个人能力参考 |
| `contribution_score` | β×goals + γ×assists + δ×d_disc | 本场个人贡献综合分 | 最佳球员评选 |
| `performance_trend` | 最近 N 场 conservative_rating 均值 | 近期状态趋势 | 折线趋势图 |
| `avg_goals_per_game` | total_goals / total_games | 每场平均进球 | 雷达图"进攻"维度 |
| `avg_assists_per_game` | total_assists / total_games | 每场平均助攻 | 雷达图"助攻"维度 |
| `avg_plus_minus` | sum(plus_minus) / total_games | 每场平均防守盘 | 雷达图"防守"维度 |
| `stability_score` | 1 / (σ / σ_initial) | 评分稳定性（σ越小越稳定） | 雷达图"稳定性"维度 |
| `composite_rating` | ts_w × conservative_rating + perf_w × performance_trend | 综合排名分（可配置权重） | 备选排名方案 |

#### 胜率估算公式

$$P(\text{player wins}) = \Phi\left(\frac{\mu_i - \bar{\mu}_{\text{team}}}{\sqrt{\sigma_i^2 + \bar{\sigma}_{\text{team}}^2 + \beta^2}}\right)$$

其中 $\Phi$ 为标准正态 CDF，$\beta$ 为 OpenSkill 内部性能方差参数（默认 `beta=25/6`）。

实现上可以用 `openskill.predict_win()` 直接计算：
```python
# 预测 player 在 team_a vs team_b 中获胜的概率
win_prob = model.predict_win([[rating_a1, ...], [rating_b1, ...]])
```

---

### 4.2 队伍维度

| 参数 | 计算方式 | 含义 |
|------|---------|------|
| `team_strength` | sum(μ_i) / n | 队伍平均技能均值 |
| `team_uncertainty` | sum(σ_i) / n | 队伍平均不确定性 |
| `balance_score` | 1 - \|μ_a - μ_b\| / max(μ_a, μ_b) | 两队平衡度（1=完全平衡，0=完全失衡） |
| `win_probability` | `model.predict_win([[team_a], [team_b]])` | 内战前预测胜率 |

**队伍平衡分的使用场景**：管理员在分配内战阵容时，系统实时显示当前分配的平衡分，辅助调整到接近 `balance_score ≈ 0.95`。

---

### 4.3 雷达图五维数据（前端可视化）

在 `GET /api/v1/players/{id}` 返回的面板数据中，五个维度需要**队内归一化**到 [0, 100]：

```python
def build_radar_stats(player: Player, all_players: list[Player]) -> RadarStats:
    """
    构建个人能力雷达图数据，以队内最大值作为100分基准。
    避免绝对值导致弱队整体分数偏低的问题。
    """
    def normalize(value: float, all_values: list[float]) -> float:
        max_val = max(all_values) or 1.0
        return min(100.0, (value / max_val) * 100.0)

    return RadarStats(
        # 进攻：每场平均进球数，归一化到队内最高值
        attack=normalize(
            player.total_goals / max(player.total_games, 1),
            [p.total_goals / max(p.total_games, 1) for p in all_players]
        ),
        # 助攻：每场平均助攻数
        assist=normalize(
            player.total_assists / max(player.total_games, 1),
            [p.total_assists / max(p.total_games, 1) for p in all_players]
        ),
        # 防守：每场平均 plus_minus（D盘次数）
        defense=normalize(
            player.total_plus_minus / max(player.total_games, 1),
            [p.total_plus_minus / max(p.total_games, 1) for p in all_players]
        ),
        # 胜率：直接百分比，无需归一化（本身就是0-100）
        win_rate=player.wins / max(player.total_games, 1) * 100,
        # 稳定性：σ越小越稳，用 (σ_initial - σ) / σ_initial 归一化
        stability=max(0.0, (8.333 - player.sigma) / 8.333 * 100),
    )
```

---

## 5. 实现方案总览

### 5.1 `engine.py` 模块结构

```python
# backend/app/rating_engine/engine.py

from openskill.models import PlackettLuce
from openskill.models.weng_lin.common import Rating

class RatingEngine:
    """OpenSkill 评分引擎，支持 Level 0-3 数据降级和 per-team 系数配置。"""

    def __init__(self):
        # mu=25, sigma=25/3, beta=25/6, tau=25/300（防止σ过度收窄）
        self.model = PlackettLuce(mu=25.0, sigma=8.333, beta=4.167, tau=0.083)

    def calculate(
        self,
        home_team: list[PlayerIn],
        away_team: list[PlayerIn],   # 外战时为虚拟对手
        score_home: int,
        score_away: int,
        match_players: list[MatchPlayerData] | None,
        data_level: int,
        settings: TeamSettings,
    ) -> list[PlayerRatingResult]:
        """核心计算入口，根据 data_level 选择对应的计算路径。"""

    def preview_balance(
        self,
        team_a: list[PlayerIn],
        team_b: list[PlayerIn],
    ) -> BalancePreview:
        """赛前队伍平衡度预览，不写入数据库。"""

    def _build_virtual_opponent(
        self, strength: int, n_players: int
    ) -> list[Rating]:
        """将对手强度(1-10)转换为虚拟对手 Rating 列表。"""
```

### 5.2 数据库新增 `team_settings` 表

```python
# backend/app/models/team_settings.py

class TeamSettings(Base):
    __tablename__ = "team_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), unique=True)
    
    # 个人贡献系数
    alpha: Mapped[float] = mapped_column(default=0.3)   # 贡献调整幅度
    beta: Mapped[float] = mapped_column(default=0.6)    # 进球权重
    gamma: Mapped[float] = mapped_column(default=0.4)   # 助攻权重
    d_disc_weight: Mapped[float] = mapped_column(default=0.3)  # 防守盘权重
    
    # 综合排名权重
    composite_ts_weight: Mapped[float] = mapped_column(default=0.85)
    composite_perf_weight: Mapped[float] = mapped_column(default=0.15)
    
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_by: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=True)
```

### 5.3 RatingHistory 追加系数快照

```python
class RatingHistory(Base):
    __tablename__ = "rating_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"))
    
    mu_before: Mapped[float]
    sigma_before: Mapped[float]
    mu_after: Mapped[float]
    sigma_after: Mapped[float]
    delta_mu: Mapped[float]        # = mu_after - mu_before
    
    data_level: Mapped[int]        # 本场使用的数据等级
    contribution_score: Mapped[float | None]  # 个人贡献分（Level 2/3 才有）
    
    # 系数快照（审计用，不随 team_settings 修改而变化）
    alpha_used: Mapped[float | None]
    beta_used: Mapped[float | None]
    gamma_used: Mapped[float | None]
    
    is_override: Mapped[bool] = mapped_column(default=False)  # 是否为管理员修正
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

---

## 6. 参数调整指南

供管理员理解各系数对排行榜的实际影响：

| 系数 | 调大效果 | 调小效果 | 建议范围 |
|------|---------|---------|---------|
| `alpha` | 个人贡献影响更大，MVP 更突出 | 更接近纯团队评分 | 0.1 ~ 0.5 |
| `beta` (进球权重) | 进球型前锋评分提升更快 | 进球不那么重要 | 0.3 ~ 1.0 |
| `gamma` (助攻权重) | 组织型球员评分受益 | 助攻贡献被淡化 | 0.2 ~ 0.8 |
| `d_disc_weight` (防守盘) | 防守型球员评分受益 | 纯进攻导向队伍选择 | 0.1 ~ 0.5 |
| `composite_ts_weight` | 更重视长期稳定性 | 更看重近期表现 | 0.7 ~ 0.95 |

> **建议**：新队首先使用默认值跑满 10-20 场比赛，观察排行榜是否合理，再根据队伍风格微调。大幅修改系数（如 alpha > 0.6）会使评分波动增大，在比赛场数少的情况下可信度下降。

---

## 7. 与原 Solar System MIX 2.0 的对比

| 对比项 | Solar System MIX 2.0（Excel） | EaglesPower（OpenSkill） |
|--------|-------------------------------|--------------------------|
| 算法基础 | 手动加权公式 | Weng-Lin 贝叶斯推断 |
| 新人初始分 | 固定值（人工设置） | μ=25, σ=8.333（自动校准） |
| 对手实力感知 | 无（所有比赛权重相同） | ✅ 赢强队涨更多 |
| 数据不完整处理 | 人工判断 | ✅ Level 0-3 自动降级 |
| 个人贡献 | 进球数直接加到评分 | ✅ 在团队结果基础上加权 |
| 多队同场 | Excel 手动计算 | ✅ PlackettLuce 原生支持 |
| 可配置性 | 修改公式 | ✅ 管理员界面调整系数 |
| 结果可追溯 | Excel 历史版本 | ✅ RatingHistory 完整审计 |

---

*文档版本: 1.0 | 对应代码: `backend/app/rating_engine/engine.py` | 最后更新: 2026-03-12*
