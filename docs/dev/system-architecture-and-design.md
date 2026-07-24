# EaglesPower 系统架构与设计说明

> 目标：帮助你快速理解系统底层原理，并能沿着文档直接定位工程代码。

## 1. 系统定位

EaglesPower 是一个围绕飞盘比赛数据录入与评级的全栈系统，核心是“比赛结果 + 个人贡献 + 事件奖惩”的分层评分模型。

- 前端：Vue 3 + TypeScript + Vant，负责登录、录入、审批、排行榜与队伍管理。
- 后端：FastAPI + SQLAlchemy + Alembic，负责鉴权、业务编排、评分计算与持久化。
- 核心算法：OpenSkill PlackettLuce + 贡献加权 + 特殊事件调整 + 化学值。

## 2. 总体架构视图

见图：

- docs/diagrams/system-overall-architecture.mmd
- docs/diagrams/match-rating-sequence.mmd
- docs/diagrams/code-navigation-map.mmd

### 2.1 系统分层图

![system-overall-architecture](diagrams/system-overall-architecture.png)

### 2.2 比赛录入到评分时序图

![match-rating-sequence](diagrams/match-rating-sequence.png)

### 2.3 代码导航图

![code-navigation-map](diagrams/code-navigation-map.png)

## 3. 核心业务链路

### 3.1 从前端录入到评分落库

1. 前端录入页收集比赛信息、阵容、Level 和统计项，构造 payload 后提交。
2. 后端 matches 端点根据用户角色决定“直接结算”还是“待审批”。
3. match_service 自动探测实际 data_level，创建 Match / MatchPlayer / MatchEvent。
4. 对于 auto_approve 或审批通过的比赛，rating_service 调用 rating_engine 完成计算并写回：
   - MatchPlayer.mu_before / mu_after
   - Player.mu / sigma / conservative_rating
   - RatingHistory 审计轨迹
   - PlayerChemistry 双人化学值

### 3.2 数据录入 Level 的实际影响

系统中 data_level 不只是展示字段，而是直接改变评分分支。

- Level 0：不更新评分（返回空结果）。
- Level 1：只用比分驱动 OpenSkill 基础更新，所有球员共享队伍结果逻辑，不看个人统计。
- Level 2：在 Level 1 基础上，增加“进球 + 助攻”贡献权重，对每个球员的 Δmu 做差异化放大或缩小。
- Level 3：在 Level 2 基础上，再引入 plus_minus 的防守权重，进一步放大攻防两端差异。

补充：Break 奖励与失误惩罚是叠加在上述结果之后的，和 Level 2/3 常一起出现，但代码上属于后处理层。

## 4. 底层原理拆解

### 4.1 OpenSkill 基础层

后端用 PlackettLuce 模型按比分进行贝叶斯更新，输出每人新的 mu 与 sigma。

- mu：能力均值
- sigma：不确定性
- conservative_rating：保守分，公式为 50 + mu - 3sigma

### 4.2 贡献加权层

仅在 Level >= 2 生效。核心思路：先拿到 OpenSkill 的 base delta，再按个人贡献比值做放大。

- 贡献来源：goals、assists（Level 2+）与 plus_minus（Level 3）
- 调节参数：alpha、beta、gamma、defense_weight
- 胜者保底：winner_floor_factor，避免“赢球但贡献低”被反向扣分

### 4.3 特殊事件奖惩层

在 rating_service 写回前叠加：

- Break goal：按 break_bonus_per_goal 增加 mu
- Turnover：按 turnover_penalty 扣减 mu，并增加 sigma 惩罚

这使系统具备“结果导向 + 过程行为约束”的复合反馈特性。

### 4.4 外战虚拟对手层

外战没有真实对手阵容时，系统按 opponent_strength 线性映射出虚拟对手 mu，并用固定 sigma 建模，再参与 OpenSkill 计算。

- 这样保留了 OpenSkill 的统计一致性
- external_impact_multiplier 再整体缩放外战对评分影响

### 4.5 化学值层

以同队两人作为 pair 单位更新：

- co_matches：共同参赛次数
- co_wins：共同胜场
- combo_count：进球-助攻连线次数

最后用胜率、配合率和置信因子合成 chemistry_score，避免小样本过拟合。

## 5. 关键模块与职责

### 5.1 前端

- API 客户端：统一 token 注入与响应解包
- 路由守卫：权限与建队状态控制
- 录入页：按 Level 动态呈现输入项，减少错误录入
- 管理页：审批与参数调优入口（超管支持按队配置）

### 5.2 后端 API

- app/main.py：FastAPI 生命周期、CORS、路由挂载
- api/v1/endpoints/matches.py：比赛提交、审批、查询、编辑、删除
- services/match_service.py：比赛数据落库与状态机
- services/rating_service.py：评分写回与化学值更新

### 5.3 评分引擎与模型

- rating_engine/engine.py：OpenSkill 计算、贡献加权、外战建模
- models/match.py：Match / MatchPlayer / MatchEvent / RatingHistory / TeamSettings / PlayerChemistry
- models/player.py：玩家账户、角色、评级字段与累计统计

## 6. 请求到代码的阅读索引

建议按下面顺序读源码：

1. 前端录入入口
   - [frontend/src/views/MatchInputView.vue](../frontend/src/views/MatchInputView.vue)
2. 提交 API 与权限
   - [backend/app/api/v1/endpoints/matches.py](../backend/app/api/v1/endpoints/matches.py)
3. 比赛数据落库与 Level 判定
   - [backend/app/services/match_service.py](../backend/app/services/match_service.py)
4. 评分计算主逻辑
   - [backend/app/rating_engine/engine.py](../backend/app/rating_engine/engine.py)
5. 评分写回与化学值
   - [backend/app/services/rating_service.py](../backend/app/services/rating_service.py)
6. 数据结构定义
   - [backend/app/models/match.py](../backend/app/models/match.py)
   - [backend/app/models/player.py](../backend/app/models/player.py)

## 7. 数据一致性与可追溯设计

系统通过两层机制保证可追溯：

- MatchPlayer 保存赛前赛后评分快照
- RatingHistory 记录每次结算原因（match_result / admin_correction / rerate）

这使得“审批修改、历史重算、删除回退”都可以有审计依据。

## 8. 你最值得优先看的原理点

如果时间有限，优先理解以下三点：

1. Level 切换本质上是评分分支切换，不是仅仅数据字段多寡。
2. 引擎计算与事件奖惩是两段式，便于扩展新奖惩规则。
3. TeamSettings 已支持队伍级参数隔离，为 A/B 测试和策略差异化打下基础。
