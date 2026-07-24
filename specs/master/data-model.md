# 数据模型: EaglesPower

**阶段**: 1 (设计)
**日期**: 2026-03-11
**基于**: specs/master/research.md + docs/architecture.md

---

## 实体关系概览

```
Team (1) ──── (N) Player
Team (1) ──── (1) TeamSettings
Player (N) ──── (N) Match  [通过 MatchPlayer]
Match (1) ──── (N) MatchPlayer
Match (1) ──── (N) RatingHistory
Player (1) ──── (N) RatingHistory
Player (N) ──── (N) Player  [通过 PlayerChemistry]
Team (1) ──── (N) TeamPost  [留言板]
```

---

## 实体定义

### 1. Team（队伍）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, autoincrement | 队伍 ID |
| `name` | String(100) | UNIQUE, NOT NULL | 队伍名称 |
| `created_at` | DateTime | NOT NULL, default=now | 创建时间 |
| `is_active` | Boolean | NOT NULL, default=True | 队伍是否激活（解散标记） |

---

### 2. Player（队员）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, autoincrement | 队员 ID |
| `team_id` | Integer | FK(team.id), NOT NULL | 所属队伍 |
| `username` | String(20) | UNIQUE, NOT NULL | 账号（6–20 位字母数字） |
| `password_hash` | String(256) | NOT NULL | bcrypt 哈希，永不明文存储 |
| `display_name` | String(50) | NULLABLE | 展示姓名（默认同 username） |
| `role` | Enum | NOT NULL, default='member' | `owner` / `admin` / `member` |
| `status` | Enum | NOT NULL, default='pending' | `pending` / `active` / `rejected` |
| `mu` | Float | NOT NULL, default=25.0 | OpenSkill 技能均值 |
| `sigma` | Float | NOT NULL, default=8.333 | OpenSkill 不确定性 |
| `conservative_rating` | Float | NOT NULL, default=0.0 | μ - 3σ（保守评分，排行榜排序依据）|
| `total_goals` | Integer | NOT NULL, default=0 | 累计进球数 |
| `total_assists` | Integer | NOT NULL, default=0 | 累计助攻数 |
| `total_plus_minus` | Integer | NOT NULL, default=0 | 累计防守盘净值 |
| `total_matches` | Integer | NOT NULL, default=0 | 参赛场次 |
| `total_wins` | Integer | NOT NULL, default=0 | 胜场次数 |
| `created_at` | DateTime | NOT NULL, default=now | 注册时间 |
| `approved_at` | DateTime | NULLABLE | 管理员审批时间 |
| `approved_by` | Integer | FK(player.id), NULLABLE | 审批管理员 ID |

**验证规则**:
- `username`: 正则 `^[a-zA-Z0-9]{6,20}$`
- `password`（注册时）: 最少 8 位，由 Pydantic Schema 校验
- `conservative_rating` 由 `engine.py` 自动计算，不接受外部直接写入
- `role` 变更只能由 `owner` 操作（指定/撤销 admin）

**状态转换**:
```
[新注册] → pending
pending → active    (admin/owner 审批)
pending → rejected  (admin/owner 拒绝)
active  → rejected  (admin/owner 封禁，极少数情况)
```

---

### 3. Match（比赛记录）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, autoincrement | 比赛 ID |
| `team_id` | Integer | FK(team.id), NOT NULL | 所属队伍 |
| `match_type` | Enum | NOT NULL | `internal`（内战）/ `external`（外战） |
| `game_type` | Enum | NOT NULL, default='ultimate' | `ultimate`（极限飞盘）/ `goal`（目标飞盘） |
| `data_level` | Integer | NOT NULL, default=0 | 数据完整性等级 0–3 |
| `team_a_score` | Integer | NOT NULL | A 队得分 |
| `team_b_score` | Integer | NOT NULL | B 队得分 |
| `opponent_strength` | Integer | NULLABLE | 外战对手强度 1–10（内战为 NULL） |
| `match_date` | DateTime | NOT NULL | 比赛日期时间 |
| `duration_seconds` | Integer | NULLABLE | 比赛计时（秒） |
| `status` | Enum | NOT NULL, default='draft' | `draft`/`pending_approval`/`approved`/`rejected` |
| `created_by` | Integer | FK(player.id), NOT NULL | 录入者 |
| `approved_by` | Integer | FK(player.id), NULLABLE | 审批者（admin）|
| `approved_at` | DateTime | NULLABLE | 审批时间 |
| `notes` | Text | NULLABLE | 备注信息 |
| `created_at` | DateTime | NOT NULL, default=now | 创建时间 |
| `updated_at` | DateTime | NOT NULL, onupdate=now | 最后更新时间 |

**验证规则**:
- `team_a_score`, `team_b_score`: >= 0
- `opponent_strength`: 1 <= x <= 10（外战必填）
- `data_level` 由后端根据 MatchPlayer 数据自动判断，不由前端传入

**状态转换**:
```
draft → pending_approval  (非 admin 录入者提交)
draft → approved          (admin 录入者直接提交，触发评分计算)
pending_approval → approved  (admin 审批，触发评分计算)
pending_approval → rejected  (admin 拒绝)
approved → approved       (admin 修改已审批比赛，触发评分重算)
```

---

### 4. MatchPlayer（比赛参与者）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, autoincrement | 记录 ID |
| `match_id` | Integer | FK(match.id), NOT NULL | 所属比赛 |
| `player_id` | Integer | FK(player.id), NOT NULL | 队员 |
| `team_side` | Enum | NOT NULL | `A` / `B`（内战）或 `home`（外战本队）|
| `goals` | Integer | NULLABLE | 本场进球数（Level 1+）|
| `assists` | Integer | NULLABLE | 本场助攻数（Level 2+）|
| `plus_minus` | Integer | NULLABLE | 本场防守盘净值（Level 3）|
| `mu_before` | Float | NOT NULL | 赛前 μ（评分快照）|
| `sigma_before` | Float | NOT NULL | 赛前 σ（评分快照）|
| `mu_after` | Float | NULLABLE | 赛后 μ（评分计算后填入）|
| `sigma_after` | Float | NULLABLE | 赛后 σ（评分计算后填入）|
| `is_winner` | Boolean | NULLABLE | 赛后填入：该队员所在队伍是否获胜 |

**约束**: `(match_id, player_id)` UNIQUE

---

### 5. RatingHistory（评分历史）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, autoincrement | 记录 ID |
| `player_id` | Integer | FK(player.id), NOT NULL | 队员 |
| `match_id` | Integer | FK(match.id), NOT NULL | 触发评分变更的比赛 |
| `mu_before` | Float | NOT NULL | 变更前 μ |
| `sigma_before` | Float | NOT NULL | 变更前 σ |
| `mu_after` | Float | NOT NULL | 变更后 μ |
| `sigma_after` | Float | NOT NULL | 变更后 σ |
| `conservative_before` | Float | NOT NULL | 变更前保守评分 |
| `conservative_after` | Float | NOT NULL | 变更后保守评分 |
| `delta_mu` | Float | NOT NULL | μ 变化量（可用于趋势图）|
| `reason` | String(100) | NOT NULL | `match_result` / `admin_correction` |
| `operated_by` | Integer | FK(player.id), NOT NULL | 操作者（通常是录入者或 admin）|
| `created_at` | DateTime | NOT NULL, default=now | 记录时间 |

---

### 6. TeamSettings（算法系数）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, autoincrement | 配置 ID |
| `team_id` | Integer | FK(team.id), UNIQUE, NOT NULL | 每队一条记录 |
| `alpha` | Float | NOT NULL, default=0.3 | OpenSkill 个人贡献调整幅度 |
| `beta` | Float | NOT NULL, default=0.6 | 进球得分权重 |
| `gamma` | Float | NOT NULL, default=0.4 | 助攻权重 |
| `composite_ts_weight` | Float | NOT NULL, default=0.85 | 综合分中 OS 分占比 |
| `composite_perf_weight` | Float | NOT NULL, default=0.15 | 综合分中表现分占比 |
| `updated_at` | DateTime | NOT NULL, onupdate=now | 最后更新时间 |
| `updated_by` | Integer | FK(player.id), NOT NULL | 最后修改者（owner only）|

**约束**: `composite_ts_weight + composite_perf_weight = 1.0`（后端校验）

---

### 7. PlayerChemistry（默契度）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, autoincrement | 记录 ID |
| `player_a_id` | Integer | FK(player.id), NOT NULL | 队员 A（较小 ID 在前）|
| `player_b_id` | Integer | FK(player.id), NOT NULL | 队员 B |
| `team_id` | Integer | FK(team.id), NOT NULL | 所属队伍 |
| `co_matches` | Integer | NOT NULL, default=0 | 共同参赛场次 |
| `co_wins` | Integer | NOT NULL, default=0 | 共同胜场次数 |
| `chemistry_score` | Float | NOT NULL, default=0.0 | 默契值（co_wins / co_matches * 调整系数）|
| `updated_at` | DateTime | NOT NULL, onupdate=now | 最后更新时间 |

**约束**: `(player_a_id, player_b_id, team_id)` UNIQUE；`player_a_id < player_b_id`（防止重复对）

---

### 8. MatchEvent（比赛实况事件流，可选）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, autoincrement | 事件 ID |
| `match_id` | Integer | FK(match.id), NOT NULL | 所属比赛 |
| `event_type` | Enum | NOT NULL | `goal` / `assist` / `defense` / `halftime` / `start` / `end` |
| `team_side` | Enum | NULLABLE | `A` / `B` |
| `player_id` | Integer | FK(player.id), NULLABLE | 涉及队员 |
| `assist_player_id` | Integer | FK(player.id), NULLABLE | 助攻队员（goal 事件）|
| `is_break` | Boolean | NULLABLE | 是否为 break 球（ultimate 模式）|
| `elapsed_seconds` | Integer | NULLABLE | 事件发生时的计时（秒）|
| `created_at` | DateTime | NOT NULL, default=now | 事件记录时间 |

---

### 9. TeamPost（队伍留言板）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, autoincrement | 帖子 ID |
| `team_id` | Integer | FK(team.id), NOT NULL | 所属队伍 |
| `author_id` | Integer | FK(player.id), NOT NULL | 发帖队员 |
| `content` | Text | NOT NULL | 帖子内容 |
| `created_at` | DateTime | NOT NULL, default=now | 发帖时间 |
| `updated_at` | DateTime | NULLABLE, onupdate=now | 编辑时间 |

---

## 数据库迁移策略

- 使用 Alembic 管理迁移脚本，路径 `backend/alembic/versions/`
- Docker 启动时 `run.py` 自动运行 `alembic upgrade head`
- 首次启动自动创建所有表，并插入默认 `TeamSettings`（alpha=0.3, beta=0.6, gamma=0.4）

## 索引规划

```sql
-- 排行榜查询优化
CREATE INDEX idx_player_team_conservative ON player(team_id, conservative_rating DESC);
-- 比赛历史查询优化
CREATE INDEX idx_match_player_player ON match_player(player_id, match_id);
-- 评分历史查询优化
CREATE INDEX idx_rating_history_player ON rating_history(player_id, created_at DESC);
-- 默契度查询优化
CREATE INDEX idx_chemistry_team ON player_chemistry(team_id, chemistry_score DESC);
```

## 阶段 1 章程检查（设计后复检）

| 检查项 | 状态 | 说明 |
|--------|------|------|
| team_settings 表存储算法系数，无硬编码 | ✅ PASS | 已定义，含所有章程要求字段 |
| RatingHistory 表支持追溯与修正 | ✅ PASS | 含 reason + operated_by 字段 |
| conservative_rating 不接受外部写入 | ✅ PASS | 由 engine.py 内部计算 |
| 密码字段仅存 bcrypt hash | ✅ PASS | password_hash 字段，无明文字段 |
| 数据 Level 0–3 降级支持 | ✅ PASS | MatchPlayer 字段均为 NULLABLE |
