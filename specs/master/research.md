# 研究报告: EaglesPower 整体技术方案

**阶段**: 0 (研究与澄清)
**日期**: 2026-03-11
**基于**: specs/master/spec.md + docs/EAGLESPOWER-方案设计.md + docs/architecture.md

---

## 1. 数据库选型决策

**Decision**: SQLite 作为默认数据库，通过 `.env` 中 `DATABASE_URL` 可无缝切换到 PostgreSQL。

**Rationale**:
- SQLite 单文件（`/data/eaglespower.db`），直接挂载 Docker volume，NAS 部署零配置
- 典型规模（< 40 队员，< 10,000 场比赛）SQLite 性能完全满足
- SQLAlchemy 2.0 async 模式对 SQLite 使用 `aiosqlite` 驱动，代码层无需改动即可切换 PostgreSQL
- 避免 NAS 额外运行 PostgreSQL 容器，降低资源占用（群晖低端型号内存仅 2GB）

**Alternatives considered**:
- PostgreSQL：更强的并发能力，但对于单队伍私有部署无必要；增加内存占用 ~150MB
- JSON 文件存储：无法支持复杂查询（排行榜多维度），排除

---

## 2. Docker 部署架构决策

**Decision**: 前端（Nginx + Vue 构建产物）+ 后端（FastAPI Uvicorn）双容器，单 `docker-compose.yml`，外部仅暴露 `8080` 端口。

**Rationale**:
```
用户浏览器 → :8080 (Nginx)
                ├── /* → Vue SPA 静态文件
                └── /api/* → :8000 (FastAPI Uvicorn) [内部网络]
```
- Nginx 作为反向代理统一入口，前端静态资源由 Nginx 直接服务（性能优于 FastAPI 托管）
- 后端容器仅在 Docker 内部网络暴露，不直接对外
- NAS 用户只需在 Container Manager 中映射一个端口（`8080:8080`）

**Alternatives considered**:
- Traefik 反向代理：功能过度，NAS 用户不熟悉，排除
- FastAPI 托管静态文件：可行但性能较差，且混合关注点，排除
- 单容器（supervisord 同时跑 Nginx + Uvicorn）：节省资源但违反容器单职责原则，热更新困难，排除

---

## 3. 移动端 UI 框架选型

**Decision**: Vant 4（vue3）

**Rationale**:
- 专为移动端设计，默认 44px 触控目标，手机体验无需额外适配
- 提供底部抽屉（ActionSheet）、底部导航（TabBar）、表单（Form/Field）等核心组件
- 主题定制通过 CSS 变量，可实现"玩家卡片"深色风格
- 与 Vue 3 + Pinia 官方支持良好

**Alternatives considered**:
- Element Plus：桌面端优先，移动端需要大量覆盖样式，排除
- Quasar：功能丰富但包体积大（~300KB gzip），排除
- Tailwind CSS + 无组件库：开发速度慢，移动端细节需手工处理，排除

---

## 4. OpenSkill 算法集成

**Decision**: 使用 `openskill` 6.2.0，`PlackettLuce` 模型，初始参数 `mu=25.0, sigma=8.333`。

**Rationale**:
- PlackettLuce 模型支持多队伍排名，适合内战（两队）和外战（本队 vs 虚拟对手）
- 初始参数与 TrueSkill 标准 `mu=25, sigma=25/3` 一致，对原 Solar System 用户直观
- `openskill` 库无 Microsoft TrueSkill 专利限制，可自由商业使用

**外战虚拟对手建模**:
- 对手强度 1–10 → 映射到 `mu_opp = strength * 2.5`（强度 10 对应 mu=25，与标准初始值相当）
- 虚拟对手 sigma 固定为 `8.333`（标准不确定性）
- 此映射保证强度语义直观：强度 10 的对手约等于"中等偏上"标准队伍

**Level 0–3 降级策略**:
| Level | 数据 | 评分策略 |
|-------|------|---------|
| 0 | 仅比分 | 纯 OpenSkill 队伍层更新（平均分配评分变化） |
| 1 | 比分 + 进球数 | 进球数加权 → 个人贡献系数调整 mu 变化幅度 |
| 2 | 比分 + 进球 + 助攻 | beta(进球) + gamma(助攻) 加权 |
| 3 | 完整统计（含防守盘净值） | 完整 composite_score = OpenSkill * alpha + 表现分 |

---

## 5. 认证与安全策略

**Decision**: JWT Bearer Token，7 天有效期，bcrypt 密码哈希，Pydantic 输入校验。

**Rationale**:
- 无状态 JWT 适配 NAS 单节点部署，无需 Redis session 存储
- 7 天有效期平衡安全与便利（赛季期间不需要频繁重新登录）
- bcrypt cost factor 12（passlib 默认），在 NAS ARM 芯片上约 300ms，防止暴力破解

**防枚举攻击**：登录失败统一返回"账号或密码错误"，不区分账号不存在、密码错误、账号被禁用。

**Alternatives considered**:
- Session + Cookie：需要 Redis，增加部署复杂度，排除
- OAuth2 第三方登录：仅限内联网部署，无需第三方，排除

---

## 6. 数据挂载与持久化

**Decision**: Docker named volume `eaglespower_data` 挂载到 `/data/`，SQLite 文件路径 `/data/eaglespower.db`。

```yaml
# docker-compose.yml 关键片段
volumes:
  eaglespower_data:
    driver: local
services:
  backend:
    volumes:
      - eaglespower_data:/data
```

**NAS 群晖备份指引**: 数据卷物理路径在 NAS 上为 `/volume1/docker/volumes/eaglespower_data/`，可直接由群晖 Hyper Backup 任务包含在备份中。

---

## 7. PWA 与离线支持

**Decision**: 基础 PWA（manifest + Service Worker 缓存静态资源），不做完整离线数据缓存。

**Rationale**:
- 添加 `manifest.json` 允许手机"添加到主屏幕"，体验类原生 App
- Service Worker 仅缓存静态资源（JS/CSS/fonts），API 数据不缓存（保证数据新鲜）
- 完整离线功能（本地 IndexedDB + 同步）复杂度过高，YAGNI

---

## 8. 前端图表库（雷达图 + 折线图）

**Decision**: ECharts 5（通过 `vue-echarts`）

**Rationale**:
- 支持雷达图和折线图，满足玩家卡片需求
- SVG 渲染，移动端高清屏显示效果好
- `vue-echarts` 提供 Vue 3 组件封装，使用简单

**Alternatives considered**:
- Chart.js：插件生态弱，雷达图定制有限，排除
- D3.js：功能强大但学习成本高，YAGNI，排除

---

## 9. 已解决的澄清事项

| 问题 | 结论 |
|------|------|
| 数据库类型？ | SQLite（默认），PostgreSQL（可选切换） |
| 部署端口配置？ | 外部仅暴露 `:8080`，内部 backend`:8000` |
| 移动端 breakpoint？ | 最小支持 375px（iPhone SE），Vant 4 自适应 |
| 首次部署管理员创建？ | 第一个注册用户自动成为 owner，跳过审批 |
| 算法系数如何管理？ | 存储于 `team_settings` 表，后台管理 API 读写 |
| 对手强度映射？ | `mu_opp = strength * 2.5`（1→2.5, 10→25） |
