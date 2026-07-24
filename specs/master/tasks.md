# 任务清单: EaglesPower — 飞盘队伍 OpenSkill 评分系统

**分支**: `master` | **日期**: 2026-03-11
**规范**: [specs/master/spec.md](spec.md) | **计划**: [specs/master/plan.md](plan.md)
**数据模型**: [specs/master/data-model.md](data-model.md) | **API 合同**: [specs/master/contracts/api-contract.md](contracts/api-contract.md)

---

## 实施策略

**执行顺序原则**（用户明确要求）：
1. **底层算法优先**：`rating_engine/` 独立实现并通过完整单元测试——其他所有模块依赖其正确性
2. **核心数据流次之**：比赛录入 → 评分计算 → 排行榜输出，打通端到端核心流程
3. **认证框架并行**：后端认证基础设施可与算法开发并行，前端等后端就绪后跟进
4. **辅助功能最后**：比赛实况、留言板、CSV 导出、邮箱找回等在核心流程稳定后实现

**MVP 范围**（最小可用版本）：
- 阶段 1（基础设施）→ 阶段 2（评分引擎 + 单元测试）→ 阶段 3（认证基础）→ 阶段 4（比赛录入 + 评分集成）→ 阶段 5（排行榜 + 玩家卡片）

---

## 依赖关系图

```
阶段 1: 基础设施
  └─ 阶段 2: 评分引擎 ← MVP 核心，先行
      └─ 阶段 4: 比赛录入 + 评分集成
          └─ 阶段 5: 排行榜 + 玩家面板
  └─ 阶段 3: 认证 + 用户管理（与阶段 2 可并行）
      └─ 阶段 4
          └─ 阶段 5
阶段 5 稳定后：
  └─ 阶段 6: 比赛实况 + 高级录入
  └─ 阶段 7: 辅助功能（导出、留言板、邮箱找回）
  └─ 阶段 8: Docker 部署 + 完善
```

---

## 阶段 1: 项目基础设施

> **目标**: 建立可运行的开发环境。后续所有任务的前提。

- [X] T001 检查并补全后端依赖声明 `backend/pyproject.toml`（openskill 6.2.0 / aiosqlite / python-jose / passlib[bcrypt] / pytest-asyncio / httpx）
- [X] T002 实现 `backend/app/core/config.py`：Pydantic BaseSettings，读取 `.env`（SECRET_KEY、DATABASE_URL、ALGORITHM、ACCESS_TOKEN_EXPIRE_DAYS）
- [X] T003 实现 `backend/app/core/database.py`：SQLAlchemy 2.0 async engine + AsyncSession + `get_db` 依赖
- [X] T004 创建 `backend/.env.example`，补全所有必填环境变量模板（含默认值说明）
- [X] T005 [P] 实现全部 ORM 模型 `backend/app/models/`：Team、Player、Match、MatchPlayer、RatingHistory、TeamSettings、PlayerChemistry、MatchEvent、TeamPost（参照 data-model.md）
- [X] T006 [P] 创建 Alembic 初始迁移脚本 `backend/alembic/versions/`（`alembic revision --autogenerate -m "initial"`），确保 `alembic upgrade head` 成功建表
- [X] T007 [P] 安装前端依赖：更新 `frontend/package.json`（vant、pinia、vue-router、axios、echarts、vue-echarts）
- [X] T008 实现 `backend/app/main.py`：FastAPI 实例、CORS 配置、路由注册占位、`GET /health` 端点（返回 `{code:0, data:{status:"ok"}}`）
- [X] T009 配置 pytest `backend/tests/conftest.py`：测试用 SQLite 内存数据库 + AsyncClient fixture

> ✅ **检查点 1**：`uv run uvicorn app.main:app` 启动成功；`GET /health` 返回 200；`alembic upgrade head` 无报错；`pytest` 运行通过（空测试套件）

---

## 阶段 2: OpenSkill 评分引擎（优先实现，优先测试）

> **目标**: 独立、完整的评分引擎，与 Web 层完全解耦，通过全部单元测试后方可推进其他阶段。
> **依赖**: 阶段 1（TeamSettings ORM 可用）

### US3 — 基础评分：内战更新 μ/σ (P1)

**独立测试标准**: 构造 3v3 内战数据（无需数据库），调用 `RatingEngine.calculate()`，断言胜队 μ 增加 / 败队 μ 减少 / 所有人 σ 收窄

- [X] T010 [US3] 定义 `RatingEngine` 输入数据结构（纯 dataclass，不依赖 ORM）：`MatchData`、`PlayerRatingInput`、`PlayerRatingOutput` 在 `backend/app/rating_engine/engine.py`
- [X] T011 [US3] 实现 `RatingEngine.__init__`：接收 `TeamSettings` 参数对象（alpha/beta/gamma/composite_ts_weight/composite_perf_weight/chem_w1/chem_w2），不读全局常量
- [X] T012 [US3] 实现 `RatingEngine.calculate_internal(match_data)` —— 内战评分：PlackettLuce 模型，胜队排名=1/败队排名=2，输出每位参与者 `mu_after`, `sigma_after`, `conservative_rating_after`, `delta_mu`
- [X] T013 [US3] 实现个人贡献加权逻辑（Level 2/3）：`adjusted_Δμ = Δμ_base * (1 + alpha * (contrib_i/mean_contrib - 1))`，胜队下限 = `0.1 * Δμ_base`（防止负值）
- [X] T014 [US3] 实现 Level 0/1 降级路径：无个人统计时退化为纯 OpenSkill 队伍层更新（不抛错）
- [X] T015 [US3] **单元测试** `backend/tests/unit/test_engine_internal.py`：
  - 测试 Level 0：3v3，A 队胜 → 胜队 μ 增↑，败队 μ 减↓，所有人 σ 收窄
  - 测试 Level 1：含进球统计，进球多的队员 μ 变化幅度更大
  - 测试 Level 2：含进球+助攻，alpha=0 时结果退化为纯 OS（无个人加权）
  - 测试 Level 3：完整统计，plus_minus 参与贡献分计算
  - 测试平局：μ 变化极小，σ 正常收窄
  - 测试非对称人数（7v6）：正常执行不报错

> ✅ **检查点 2a**: `pytest tests/unit/test_engine_internal.py -v` 全部 PASS

### US3 — 外战评分：虚拟对手建模 (P1)

**独立测试标准**: 外战（本队赢，对手强度=9）后队员μ增幅 > 外战（输给弱队）后队员μ减幅——符合直觉

- [X] T016 [US3] 实现 `RatingEngine.calculate_external(match_data, opponent_strength)`：映射 `mu_opp = opponent_strength * 2.5`，sigma_opp = 8.333，构造虚拟对手参与 PlackettLuce
- [X] T017 [US3] **单元测试** `backend/tests/unit/test_engine_external.py`：
  - 测试赢强队（强度=9）μ 增幅 > 赢弱队（强度=2）μ 增幅
  - 测试输强队 μ 下降幅度 < 输弱队 μ 下降幅度
  - 测试强度边界：强度=1、强度=10 均正常执行

> ✅ **检查点 2b**: `pytest tests/unit/test_engine_external.py -v` 全部 PASS

### US3 — 默契度算法 (P2)

**独立测试标准**: 喂入 5 场比赛数据（A 和 B 3 场共同胜），计算 chemistry_score，断言大于 A 和 C（0 场共同胜）的值

- [X] T018 [US3] 实现 `ChemistryCalculator.update(match_data)` in `backend/app/rating_engine/chemistry.py`：更新 co_matches / co_wins / combo_count，计算 chemistry_score
- [X] T019 [US3] **单元测试** `backend/tests/unit/test_chemistry.py`：
  - 测试 3 场及以上共同参赛才参与排行（<3 场不计入）
  - 测试 A+B 默契度 > A+C（C 与 A 没赢过）
  - 测试对称性：`chemistry(A,B) == chemistry(B,A)`
  - 测试 combo_count 双向累计

> ✅ **检查点 2c**: `pytest tests/unit/ -v` 全部 PASS（算法模块完整测试通过）

---

## 阶段 3: 认证系统（与阶段 2 可并行）

> **目标**: 用户注册/登录/JWT/角色/审批流程完整可用。
> **依赖**: 阶段 1（Player ORM、Team ORM、数据库）

### US1 — 管理员首次初始化队伍 (P1)

**独立测试标准**: 全新数据库 → 注册第一个用户 → 该用户 role=owner / status=active，队伍记录已创建

- [X] T020 [US1] 实现 `backend/app/core/security.py`：`hash_password(plain)` / `verify_password(plain, hashed)` / `create_access_token(data)` / `decode_access_token(token)`
- [X] T021 [US1] 实现 `backend/app/schemas/auth.py`：`RegisterRequest`（username/password/display_name/team_name）、`LoginRequest`、`TokenResponse`
- [X] T022 [US1] 实现 `backend/app/schemas/player.py`：`PlayerCreate`、`PlayerRead`（含 mu/sigma/conservative_rating/role/status）、`PlayerUpdate`
- [X] T023 [US1] 实现 `backend/app/api/v1/endpoints/auth.py`：`POST /auth/register`（检测是否首次→owner；否则→pending）、`POST /auth/login`（bcrypt 验证→签发 JWT）、`GET /auth/me`
- [X] T024 [US1] 实现 `backend/app/api/v1/deps.py`：`get_current_user(token)` / `require_admin` / `require_owner` 依赖
- [X] T025 [US1] **集成测试** `backend/tests/integration/test_auth.py`：
  - 测试首个注册用户→role=owner、status=active
  - 测试第二个注册用户→status=pending，登录返回 403
  - 测试正确密码登录→返回 access_token；错误密码→401
  - 测试 pending 用户登录→403
  - 测试 `GET /auth/me` 携带有效 token→200；无 token→401

> ✅ **检查点 3a**: `pytest tests/integration/test_auth.py -v` 全部 PASS

### US2 — 普通成员注册与审批流 (P1)

**独立测试标准**: 注册→pending；admin 批准→active；rejected 用户登录→403

- [X] T026 [US2] 实现 `backend/app/api/v1/endpoints/players.py`：`GET /players`（分页/status 过滤）、`PUT /players/{id}`（admin 更新 status；owner 更新 role）、`GET /players/{id}`
- [X] T027 [US2] **集成测试** `backend/tests/integration/test_players.py`：
  - 测试 admin 把 pending 用户改为 active → 用户可登录
  - 测试非 admin 无法修改他人 status → 403
  - 测试 owner 可指定/撤销 admin 角色

### US4 — 管理员直接创建激活账号 (P2)

- [X] T028 [US4] 在 `POST /players` 端点中支持 admin 创建 status=active 的账号（非 admin 创建时强制 pending）
- [X] T029 [US4] **集成测试**：admin 创建 active 账号→该账号直接可登录；非 admin 尝试创建 active 账号→强制 pending

### US6 — 主理人管理 admin 权限 (P1)

- [X] T030 [US6] 在 `PUT /players/{id}` 中实现角色变更权限控制：只有 owner 可修改 role；owner 本身角色不可降级
- [X] T031 [US6] **集成测试**：owner 指定 admin 成功；admin 尝试指定其他 admin → 403

> ✅ **检查点 3b**: `pytest tests/integration/test_players.py tests/integration/test_auth.py -v` 全部 PASS

---

## 阶段 4: 比赛录入 + 评分集成（核心数据流）

> **目标**: 打通"创建比赛 → 调用评分引擎 → 更新 Player μ/σ → 写入 RatingHistory"完整链路。
> **依赖**: 阶段 2（RatingEngine 通过测试）+ 阶段 3（认证就绪）

### US-Match1 — 内战录入（两队对战） (P1)

**独立测试标准**: `POST /matches` → match.status=approved → Player.mu/sigma 已更新 → RatingHistory 有新记录

- [X] T032 [US-Match1] 实现 `backend/app/schemas/match.py`：`MatchCreate`（含 team_a_players/team_b_players/players 个人统计/events）、`MatchRead`、`MatchPlayerCreate`
- [X] T033 [US-Match1] 实现 data_level 自动判断逻辑（服务层 `backend/app/services/match_service.py`）：根据 MatchPlayer 数据判断 Level 0–3
- [X] T034 [US-Match1] 实现 `backend/app/api/v1/endpoints/matches.py`：`POST /matches`（创建比赛 + 调用评分引擎 + 更新 Player 累计统计 + 写 RatingHistory + 更新 PlayerChemistry）
- [X] T035 [US-Match1] 实现评分引擎集成服务 `backend/app/services/rating_service.py`：从 `TeamSettings` 表加载系数 → 调用 `RatingEngine` → 批量更新 Player ORM → 批量插入 RatingHistory
- [X] T036 [US-Match1] 实现 `GET /matches`（分页列表，支持 status/match_type 过滤）、`GET /matches/{id}`（含参与者统计详情）
- [X] T037 [US-Match1] **集成测试** `backend/tests/integration/test_matches.py`：
  - 测试 admin 创建内战 → status=approved → Player.mu 已变化 → RatingHistory 有记录
  - 测试非 admin 创建比赛 → status=pending_approval，评分未更新
  - 测试 Level 0 比赛提交不报错（无个人统计）
  - 测试 Level 3 比赛：有进球/助攻/plus_minus，评分变化幅度符合预期

> ✅ **检查点 4a**: 端到端：创建内战→评分更新→RatingHistory 有记录，集成测试全 PASS

### US-Match2 — 外战录入（对阵外队） (P1)

- [X] T038 [US-Match2] 在 `POST /matches` 中支持 `match_type=external`：验证 opponent_strength 必填（1–10），调用 `RatingEngine.calculate_external()`
- [X] T039 [US-Match2] **集成测试**：外战提交（对手强度=9，本队赢）→ 评分增幅比赢弱队时更大（通过数据库查询验证 delta_mu 差异）

### US-Match3 — 快速补录（仅比分） (P2)

- [X] T040 [US-Match3] 支持 Level 0 快速录入路径：仅提供阵容+比分，data_level 自动设为 0，评分使用纯 OS

### US-Match4 — 管理员审批与赛后修改 (P2)

- [X] T041 [US-Match4] 实现 `PUT /matches/{id}`（admin 审批：pending_approval → approved，触发评分计算；admin 修改已审批比赛，触发评分重算并追加 RatingHistory reason=admin_correction）
- [X] T042 [US-Match4] **集成测试**：admin 修改已有比赛比分 → 相关 Player.mu 发生变化 → RatingHistory 新记录 reason=admin_correction

> ✅ **检查点 4b**: `pytest tests/integration/test_matches.py -v` 全部 PASS；`GET /health` 仍返回 200

---

## 阶段 5: 排行榜 + 玩家面板（核心输出）

> **目标**: 提供 6 维度排行榜和完整个人玩家卡片数据。
> **依赖**: 阶段 4（Player 评分数据已更新，RatingHistory 有记录）

### US-Rank1 — 排行榜（6 维度） (P1)

**独立测试标准**: 登录 → `GET /rankings?tab=conservative` → 列表按 conservative_rating 降序 → 切换 tab=stable → 按 σ 升序

- [X] T043 [US-Rank1] 实现 `backend/app/api/v1/endpoints/rankings.py`：`GET /rankings` 支持 tab 参数（conservative/stable/goals/assists/defense/chemistry），分页返回，未登录返回 401
- [X] T044 [US-Rank1] 实现 chemistry tab：查询 PlayerChemistry，共同参赛 ≥ 3 场的配对按 chemistry_score 降序
- [X] T045 [US-Rank1] **集成测试** `backend/tests/integration/test_rankings.py`：
  - 测试未登录访问 → 401
  - 测试 tab=conservative → 按 conservative_rating 降序
  - 测试 tab=stable → 按 sigma 升序
  - 测试 pending/rejected 队员不出现在排行榜

### US-Rank2 — 个人玩家面板 (P1)

**独立测试标准**: `GET /rankings/me` → 返回含雷达图 5 维数据 + 最近 10 场历史曲线 + 最近 20 场比赛记录

- [X] T046 [US-Rank2] 实现 `GET /rankings/me`：聚合 Player 统计、5 维雷达图数据（attack/assist/defense/stability/win_rate）、最近 10 场 RatingHistory 曲线、最近 20 场比赛记录
- [X] T047 [US-Rank2] 实现 `GET /rankings/players/{id}`：admin 返回完整数据，普通成员返回公开字段（隐藏 μ/σ 历史详情）
- [X] T048 [US-Rank2] **集成测试**：
  - 测试 `GET /rankings/me` 返回 radar 数据结构完整
  - 测试普通成员访问他人面板 → 不含 μ/σ 历史
  - 测试 admin 访问他人面板 → 完整数据

> ✅ **检查点 5**: `pytest tests/integration/test_rankings.py -v` 全部 PASS；后端 API 层完整可用

---

## 阶段 5B: 前端核心页面（与阶段 5 后端可并行）

> **目标**: Vue 3 前端核心页面实现，移动端 375px 优先。
> **依赖**: 阶段 3（登录 API）+ 阶段 5（排行榜/玩家面板 API 稳定）

### 前端基础设施

- [X] T049 [P] 配置 `frontend/src/api/index.ts`：Axios 实例，`Authorization: Bearer` 拦截器，统一响应解包，401 自动跳转 `/login`
- [X] T050 [P] 配置 `frontend/src/router/index.ts`：路由守卫（需认证路由检查 Pinia store token）；5 条路由：/login、/register、/rankings、/profile、/match/new
- [X] T051 [P] 实现 `frontend/src/stores/auth.ts`：Pinia store，login()/logout()/fetchMe()，JWT 存入 localStorage，页面刷新后自动恢复登录状态
- [X] T052 实现 `frontend/src/App.vue`：根组件，登录后显示 Vant `van-tabbar`（5 tab：队伍/排行榜/+/比赛/我的）

### 认证页面 [US1-US3]

- [X] T053 [P] [US3] 实现 `frontend/src/views/LoginView.vue`：Vant Form，账号/密码，提交调用 POST /auth/login，成功跳转 /rankings
- [X] T054 [P] [US2] 实现 `frontend/src/views/RegisterView.vue`：注册表单（含首次注册时的队伍名字段，通过 `GET /api/v1/team/exists` 判断），提交成功弹 Dialog 提示待审批

### 排行榜页面 [US-Rank1]

- [X] T055 [US-Rank1] 实现 `frontend/src/views/RankingsView.vue`：`van-tabs`（6 个维度 tab） + `van-list` 排名列表；按 tab 调用 `GET /rankings?tab=xxx`；每行：排名/姓名/数值/趋势

### 玩家面板页面 [US-Rank2]

- [X] T056 [US-Rank2] 实现 `frontend/src/views/ProfileView.vue`：玩家卡片布局（深色主题），ECharts 雷达图（5 维）+ ECharts 折线图（近 10 场保守评分趋势）+ 比赛记录列表
- [X] T057 [US-Rank2] 实现 `frontend/src/components/PlayerCard.vue`：头像/姓名/保守评分大字/排名位置/μ/σ 数值行

### 比赛录入页面 [US-Match1/2/3]

- [X] T058 [US-Match1] 实现 `frontend/src/views/MatchInputView.vue`：Step 1（类型选择）→ Step 2（阵容分配，`van-checkbox-group`）；Step 3（数据统计）→ Step 4（确认提交）
- [X] T059 [US-Match1] 实现得分录入底部抽屉 `frontend/src/components/GoalDrawer.vue`：`van-action-sheet`，选得分者 → 选助攻者（可选）→ 确认；比分板实时更新
- [X] T060 [US-Match1] 实现比赛总结页 + 提交逻辑：展示比分/统计榜 → 点击"提交"调 `POST /matches` → 成功跳转排行榜并 `van-toast` 提示
- [X] T061 [US-Match2] 在 Step 2 中支持外战模式：对手强度 `van-stepper`（1–10）

> ✅ **检查点 5B**: 移动端（375px）可完整完成"登录→录入比赛→查看排行榜→个人面板"完整流程；手动测试通过

---

## 阶段 6: 比赛实况与高级录入

> **目标**: 比赛实况时间轴、半场逻辑、防守盘录入、Ultimate 模式 break 球。
> **依赖**: 阶段 5B（比赛录入基础页面就绪）

### US-Match1 实况扩展 (P2)

- [X] T062 [US-Match1] 实现 `frontend/src/views/MatchLiveView.vue`：比赛时间轴页面，纵向展示 MatchEvent 流（左=A队/右=B队），支持"比赛实况"按钮从主屏幕跳转
- [X] T063 [US-Match1] 实现防守盘录入底部抽屉 `frontend/src/components/DefenseDrawer.vue`：选防守方和拦截者
- [X] T064 [US-Match1] 实现半场逻辑：`van-button`"半场"→ 暂停计时 + 弹出半场确认 Dialog + 翻转性别比例记录

### MatchEvent 后端支持

- [X] T065 [P] 在 `POST /matches` 请求体中支持 `events` 数组写入 MatchEvent 表
- [X] T066 [P] 实现 `GET /matches/{id}/events`：返回该场比赛的时间轴事件流

### 比赛管理列表 (P2)

- [X] T067 [US-Match4] 实现 `frontend/src/views/MatchListView.vue`：`van-tabs`（待审批/已完成）+ `van-list`；admin 每行显示"编辑"按钮
- [X] T068 [US-Match4] 实现比赛编辑路由 `/match/edit/:id`：预填充表单数据，提交触发 `PUT /matches/{id}`

> ✅ **检查点 6**: 比赛实况时间轴完整可用，管理员可在比赛列表中进入编辑模式

---

## 阶段 7: 辅助功能

> **目标**: 非核心但用户体验重要的辅助功能。
> **依赖**: 阶段 5B（前端基础就绪）

### 历史比赛查看 [US-Rank3] (P2)

- [X] T069 [US-Rank3] 实现比赛详情页 `frontend/src/views/MatchDetailView.vue`：双方阵容 / 进球榜 / 助攻榜 / 防守榜 / Δμ（登录用户可见）
- [X] T070 [US-Rank3] 实现 `GET /matches` 公开列表接口（未登录可见基本信息，隐藏 Δμ 详情）

### 数据导出 [US-Rank4] (P2)

- [X] T071 [US-Rank4] 实现 `backend/app/api/v1/endpoints/exports.py`：`GET /exports/rankings?format=csv|xlsx`、`GET /exports/matches?format=csv|xlsx`（admin 权限，UTF-8 BOM 编码）
- [X] T072 [US-Rank4] **单元测试** `backend/tests/unit/test_export.py`：CSV 输出包含正确表头，非 admin 访问返回 403

### 留言板 [US-Rank6] (P2)

- [X] T073 [US-Rank6] 实现 `backend/app/api/v1/endpoints/team.py`：`GET /team/posts`（倒序分页）、`POST /team/posts`（active 成员）、`DELETE /team/posts/{id}`（发帖人或 admin，软删除）
- [X] T074 [US-Rank6] 实现 `frontend/src/views/TeamView.vue`：队伍信息区 + 留言板（`van-list` + 底部发布输入框），发布后乐观更新 UI
- [X] T075 [US-Rank6] **集成测试**：未登录访问 `GET /team/posts` → 401；发帖 → 其他用户可见；发帖人删除 → 软删除成功

### 管理员后台 (P2)

- [X] T076 在 `frontend/src/views/AdminView.vue` 实现：待审批成员列表（批准/拒绝）、待审批比赛列表（审批/查看）、算法系数配置（owner only）
- [X] T077 实现 `GET /team/settings`、`PUT /team/settings`（owner 权限）后端接口
- [X] T078 **集成测试**：owner 修改算法系数 → 下一场比赛使用新系数计算评分；非 owner 修改 → 403

### 邮箱找回密码 [US1-US5] (P3)

- [X] T079 [US5] 在 Player 表添加可选 `email` 字段（Alembic 迁移），`PUT /players/me/email` 绑定邮箱
- [X] T080 [US5] 实现 `POST /auth/forgot-password`（SMTP 配置时发送重置链接；未配置时返回 403 + 明确提示），`POST /auth/reset-password`（验证 token 有效期 1h，单次使用）
- [X] T081 [US5] 前端登录页"忘记密码"链接 + 重置密码页面

> ✅ **检查点 7**: 所有 P2 辅助功能可用；数据导出 CSV 可用 Excel 打开无乱码

---

## 阶段 8: 部署完善与非功能需求

> **目标**: Docker 容器化完整可用，NAS 一键部署，性能与安全验收。
> **依赖**: 所有核心功能就绪

- [X] T082 完善 `backend/Dockerfile`：多阶段构建，`python:3.11-slim`，`ENTRYPOINT ["python", "run.py"]`（run.py 自动运行 alembic upgrade head 再启动 uvicorn）
- [X] T083 完善 `frontend/Dockerfile`：`node:20-alpine` 构建阶段 + `nginx:alpine` 服务阶段，`COPY nginx.conf`
- [X] T084 完善 `frontend/nginx.conf`：`location /api/` 反向代理到 `http://backend:8000/api/`；`location /` 托管 Vue SPA（`try_files $uri $uri/ /index.html`）
- [X] T085 完善 `docker-compose.yml`：backend 服务（内部 8000，不对外）+ frontend 服务（外部 8080→内部 80）+ `eaglespower_data` named volume + healthcheck（`GET /health`）
- [X] T086 实现前端 PWA：添加 `frontend/public/manifest.json`（name/short_name/icons/theme_color）+ Service Worker 注册（Vite PWA plugin，仅缓存静态资源）
- [X] T087 [P] 实现结构化日志中间件 `backend/app/core/middleware.py`：每个请求注入 `request_id`，错误时记录 `[ERROR] [Module::Function] Message`（英文）
- [X] T088 [P] 为前端实现 `van-safe-area` 适配（iPhone 刘海屏），所有页面主体 `padding-bottom: env(safe-area-inset-bottom)`
- [X] T089 安全审查：使用 `bandit` 扫描后端代码（`uv run bandit -r app/`），修复发现的 OWASP Top 10 问题
- [ ] T090 **Docker 端到端验证**：`docker compose up -d --build` → `curl http://localhost:8080/health` 返回 200；手机浏览器 375px 完整流程通过（需在安装 Docker Desktop 的机器执行）

> ✅ **检查点 8（最终）**: `docker compose up -d` 成功启动；手机端完整流程可用；`bandit` 无高危告警；`pytest` 全量通过

---

## 依赖关系摘要

| 阶段 | 依赖 | 可并行的任务 |
|------|------|-------------|
| 阶段 1 | 无 | T005/T006/T007 可并行 |
| 阶段 2 | 阶段 1 完成 | T010→T019 串行（逐层构建引擎）|
| 阶段 3 | 阶段 1 完成 | 与阶段 2 **完全并行** |
| 阶段 4 | 阶段 2 + 阶段 3 全部通过 | T038/T039 可与 T032-T037 并行 |
| 阶段 5 | 阶段 4 完成 | T043-T048 与 T049-T061 可并行 |
| 阶段 6 | 阶段 5B 完成 | T062-T064 与 T065-T068 可并行 |
| 阶段 7 | 阶段 5 + 5B 完成 | T069-T081 大部分可并行 |
| 阶段 8 | 阶段 7 完成 | T082-T090 部分可并行 |

---

## 并行执行示例（最优路径）

**第一批（并行启动）**
- 开发者 A: 阶段 1（T001→T009）
- _（等待阶段 1 完成）_

**第二批（阶段 1 完成后并行）**
- 开发者 A: 阶段 2（T010→T019，评分引擎+测试）
- 开发者 B: 阶段 3（T020→T031，认证+用户管理）

**第三批（阶段 2+3 全通过后）**
- 阶段 4（T032→T042，比赛录入+评分集成）[完全串行，逻辑依赖强]

**第四批（阶段 4 完成后并行）**
- 开发者 A: 阶段 5 后端（T043-T048）
- 开发者 B: 阶段 5B 前端基础（T049-T052）

**第五批（阶段 5 完成后）**
- 阶段 5B 前端页面（T053-T061）

**后续按需推进**：阶段 6 → 阶段 7 → 阶段 8

---

## 统计

| 指标 | 数值 |
|------|------|
| 总任务数 | **90 个** |
| 阶段 1（基础设施） | 9 个 |
| 阶段 2（评分引擎 + 测试） | 10 个 |
| 阶段 3（认证 + 用户管理） | 12 个 |
| 阶段 4（比赛录入 + 评分集成） | 11 个 |
| 阶段 5（排行榜 + 玩家面板） | 6 个 |
| 阶段 5B（前端核心页面） | 13 个 |
| 阶段 6（实况 + 高级录入） | 7 个 |
| 阶段 7（辅助功能） | 13 个 |
| 阶段 8（部署完善） | 9 个 |
| 含测试的任务（[unit]/[integration]） | **22 个** |
| 可并行（[P] 标记）任务数 | **17 个** |
