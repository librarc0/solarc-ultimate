# 实施计划: EaglesPower — 飞盘队伍 OpenSkill 评分系统（整体）

**分支**: `master` | **日期**: 2026-03-11 | **规范**: [specs/master/spec.md](../master/spec.md)
**输入**: 来自 `/specs/master/spec.md` 的整体项目规范

**注意**: 此模板由 `/speckit.plan` 命令填充. 执行工作流程请参见 `.specify/templates/plan-template.md`.

## 摘要

EaglesPower 是替代 Solar System MIX 2.0（Excel + Python 脚本）的网页化飞盘评分系统。
核心需求：**手机端录入比赛数据 → OpenSkill 评分自动更新 → 公开排行榜与个人玩家卡片**。

**技术方案**：FastAPI 后端 + Vue 3/Vant 4 移动端优先前端 + SQLite 数据库 + Docker 一键部署于 NAS。
系统分 4 个功能域实施：① 用户认证与审批 ② 比赛录入（Level 0–3 数据分级）③ OpenSkill 评分引擎 ④ 排行榜与玩家面板。

## 技术背景

**语言/版本**: Python 3.11（后端） · TypeScript 5.x / Node.js 20（前端构建）
**主要依赖**:
- 后端: FastAPI 0.135.x · SQLAlchemy 2.0（async）· Alembic · openskill 6.2.0 · python-jose · passlib[bcrypt]
- 前端: Vue 3.4+ · Vant 4 · Pinia · Axios · Vite 5

**存储**: SQLite（开发 + NAS 默认，`/data/eaglespower.db` 挂载卷）；PostgreSQL（可选，通过 `.env` 切换 `DATABASE_URL`）
**测试**: pytest + pytest-asyncio（后端）· Vitest（前端单元）· Playwright（E2E，可选）
**目标平台**: Linux arm64/amd64 Docker 容器（群晖/QNAP/绿联 NAS）；客户端：任意现代浏览器（Chrome/Safari，375px+）
**项目类型**: 全栈 Web 应用 + PWA（渐进式网页应用）
**性能目标**: API p95 < 500ms（本地局域网）；评分计算 < 200ms（单场，< 30 人参赛）
**约束条件**: 单 Docker Compose 文件部署；SQLite 单文件持久化；移动端 3 步内完成比赛录入主流程
**规模/范围**: 单队伍私有部署，典型规模 10–40 名队员；比赛记录预计累计 < 10,000 场

## 章程检查

*门控: 必须在阶段 0 研究前通过. 阶段 1 设计后重新检查.*

### 阶段 0 前置检查（初始）

| 检查项 | 章程原则 | 状态 | 备注 |
|--------|---------|------|------|
| 后端使用 Python 3.11 + FastAPI + SQLAlchemy 2.0 | Principle I | ✅ PASS | 与章程技术栈完全一致 |
| 前端使用 Vue 3 + Vant 4 + Pinia | Principle I | ✅ PASS | 与章程技术栈完全一致 |
| 数据库使用 SQLite（NAS 友好） | Principle I | ✅ PASS | 章程允许 SQLite/PostgreSQL 切换 |
| 部署使用 Docker + Docker Compose | Principle I | ✅ PASS | NAS 一键部署 |
| 移动端 375px 首先通过测试 | Principle II | ✅ PASS | Vant 4 专为移动端设计 |
| 主流程 3 步内完成录入 | Principle II | ✅ PASS | 已在规范中明确约束 |
| API 响应 p95 < 500ms | Principle II | ✅ PASS | 已在性能目标中定义 |
| 支持 Level 0–3 数据降级 | Principle III | ✅ PASS | 已在规范非功能需求中明确 |
| RatingHistory 追溯记录 | Principle III | ✅ PASS | 架构文档已定义该表 |
| 密码 bcrypt 哈希，JWT 鉴权 | Principle IV | ✅ PASS | passlib[bcrypt] + python-jose |
| 输入经 Pydantic Schema 校验 | Principle IV | ✅ PASS | FastAPI 强制使用 Pydantic |
| 单文件不超过 500 行 | Principle V | ⚠️ 待验证 | 实施时监控，超出则拆分 |
| 算法模块独立，可单独测试 | Principle V | ✅ PASS | `rating_engine/` 独立目录 |
| `GET /health` 健康检查端点 | Principle VI | ✅ PASS | main.py 中已规划 |
| 结构化日志含 request_id | Principle VI | ✅ PASS | 中间件注入 |
| 核心算法文件注释率 ≥ 25% | Principle VII | ⚠️ 待验证 | 实施时强制检查 |
| API 端点文件注释率 ≥ 20% | Principle VII | ⚠️ 待验证 | 实施时强制检查 |
| 前端组件注释率 ≥ 15% | Principle VII | ⚠️ 待验证 | 实施时强制检查 |
| 算法系数存储于 team_settings 表，不硬编码 | 算法约束 | ✅ PASS | 架构文档已规划 |
| 所有响应统一格式 `{code, data, message}` | API 约束 | ✅ PASS | 已在 contracts 中定义 |

**门控结论**: ✅ 所有硬性门控通过，3 个"待验证"项为实施阶段监控项，不阻塞规划推进。

### 阶段 1 后置检查（设计后复检）

见下方"阶段 1 设计后重新评估"章节。

## 项目结构

### 文档(此功能)

```
specs/master/
├── plan.md              # 此文件 (/speckit.plan 命令输出)
├── research.md          # 阶段 0 输出 (/speckit.plan 命令)
├── data-model.md        # 阶段 1 输出 (/speckit.plan 命令)
├── quickstart.md        # 阶段 1 输出 (/speckit.plan 命令)
├── contracts/           # 阶段 1 输出 (/speckit.plan 命令)
│   ├── openapi.yaml     # REST API 合同
│   └── ui-contracts.md  # 前端页面合同
└── tasks.md             # 阶段 2 输出 (/speckit.tasks 命令 - 非 /speckit.plan 创建)
```

### 源代码(仓库根目录)

```
# 选项 2: Web 应用程序（前端 + 后端）
backend/
├── app/
│   ├── main.py              # FastAPI app 实例，CORS，路由注册，健康检查
│   ├── core/
│   │   ├── config.py        # Pydantic BaseSettings，读取 .env
│   │   ├── database.py      # SQLAlchemy async engine + SessionLocal
│   │   └── security.py      # JWT 签发/验证，bcrypt 哈希
│   ├── models/
│   │   ├── player.py        # Player ORM（含 role/status/mu/sigma）
│   │   ├── match.py         # Match / MatchPlayer / RatingHistory ORM
│   │   └── team_settings.py # TeamSettings ORM（算法系数）
│   ├── schemas/
│   │   ├── auth.py          # LoginRequest / TokenResponse / RegisterRequest
│   │   ├── player.py        # PlayerCreate / PlayerRead / PlayerUpdate
│   │   └── match.py         # MatchCreate / MatchRead / MatchPlayerCreate
│   ├── api/v1/
│   │   ├── router.py        # 汇总所有端点
│   │   ├── deps.py          # get_current_user / require_admin
│   │   └── endpoints/
│   │       ├── auth.py      # POST /login, POST /register
│   │       ├── players.py   # GET/PUT /players
│   │       ├── matches.py   # POST/GET/PUT /matches
│   │       └── rankings.py  # GET /rankings, GET /rankings/me
│   ├── services/            # 业务逻辑层（将来扩展）
│   └── rating_engine/
│       └── engine.py        # RatingEngine，PlackettLuce，Level 0–3 降级
├── alembic/                 # 数据库迁移脚本
├── tests/
│   ├── unit/                # rating_engine 单元测试
│   └── integration/         # API 集成测试
├── Dockerfile
└── pyproject.toml

frontend/
├── src/
│   ├── main.ts              # Vue app 挂载，全局注册 Vant 4
│   ├── App.vue              # 根组件，底部导航 TabBar
│   ├── router/index.ts      # 5 条路由（/login, /register, /rankings, /profile, /match/input）
│   ├── stores/
│   │   └── auth.ts          # Pinia store：login/logout/fetchMe，JWT 持久化
│   ├── api/index.ts         # Axios 实例，Bearer token 拦截器
│   ├── views/
│   │   ├── LoginView.vue
│   │   ├── RegisterView.vue
│   │   ├── RankingsView.vue    # 6 维度 tab 排行榜
│   │   ├── ProfileView.vue     # 玩家卡片：雷达图 + 折线图 + 比赛记录
│   │   └── MatchInputView.vue  # 比赛录入主流程（内战/外战/快速）
│   └── components/          # 复用组件（PlayerCard, RadarChart, MatchTimeline 等）
├── Dockerfile
└── package.json

docker-compose.yml           # 服务编排：backend(8000) + frontend(8080) + 数据卷
```

**结构决策**: 选用"选项 2: Web 应用程序"结构，前后端各自独立 Docker 镜像，通过 Nginx 反向代理（frontend 容器）将 `/api/` 请求转发到 backend 容器，实现单端口对外暴露（`:8080`）。

## 复杂度跟踪

> **仅在章程检查有必须证明的违规时填写**

| 违规 | 为什么需要 | 拒绝更简单替代方案的原因 |
|-----------|------------|-------------------------------------|
| 前后端分离双容器 | 前端需要静态资源 CDN 级 Nginx 加速；后端需要独立扩展 | 单容器 SSR 方案对 Vue 3 工程化成本更高，且失去热更新开发体验 |
| Level 0–3 数据分级逻辑 | 章程 Principle III 强制要求；不完整数据不拒绝 | 直接要求完整数据会导致赛场录入失败，影响核心使用场景 |
