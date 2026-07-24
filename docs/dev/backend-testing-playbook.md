# EAGLESPOWER 后端测试作战手册

## 1. 文档目标

这份文档用于统一后端测试标准，解决三个核心问题：

1. 现在到底测了什么。
2. 哪些核心能力还没测到。
3. 如何在测试阶段提前拦截模型变更与迁移不同步的问题。

适用范围：

- backend 目录下的 API、服务层、评分引擎、数据库迁移。
- 日常开发自测、合并前验收、发布前回归。

关联文档：

- 一页速查版：docs/backend-testing-quick-reference.md

---

## 2. 测试分层策略

### 2.1 分层定义

1. 单元测试（unit）
- 验证纯业务逻辑和服务函数。
- 目标是快、稳定、问题定位精确。

2. 集成测试（integration）
- 验证 API 路由、权限、数据库读写、端到端业务流程。
- 目标是保障用户真实路径可用。

3. 迁移测试（migration smoke）
- 验证 Alembic 从空库升级到 head 的可靠性。
- 对比 ORM 元数据与迁移后数据库结构，拦截“模型改了但迁移没补”。

### 2.2 当前默认质量门禁

1. 核心后端回归任务已纳入 migration 测试。
2. pytest 已设置 Pydantic V2 弃用告警为失败。
3. Alembic 配置已修正 path_separator，避免配置层弃用告警。

---

## 3. 当前测试清单（已覆盖）

### 3.1 集成测试

1. 认证与账户
- 文件：backend/tests/integration/test_auth.py
- 覆盖：注册、登录、密码重置、token 校验、拒绝状态处理。

2. 比赛主流程
- 文件：backend/tests/integration/test_matches.py
- 覆盖：提交、审批、拒绝、编辑、删除、详情、事件流、评分结算。

3. 实况草稿与断点续录
- 文件：backend/tests/integration/test_matches.py
- 覆盖：
  - 草稿创建、保存、结束、放弃。
  - 事件幂等、seq 冲突。
  - 公共未完成列表。
  - 进入录入锁与并发冲突拦截。
  - 最终提交人身份、最近保存人身份。

4. 排行榜
- 文件：backend/tests/integration/test_rankings.py
- 覆盖：排序、分页、字段完整性、球员面板。

5. 队伍设置
- 文件：backend/tests/integration/test_team_settings.py
- 覆盖：读取、修改、权限、参数影响。

6. 失误机制
- 文件：backend/tests/integration/test_turnovers.py
- 覆盖：失误事件、统计累加、评分惩罚与 sigma 影响。

### 3.2 单元测试

1. 比赛服务核心
- 文件：backend/tests/unit/test_match_service_core.py

2. 数据等级判定
- 文件：backend/tests/unit/test_match_service_levels.py

3. 评分服务核心
- 文件：backend/tests/unit/test_rating_service_core.py

4. 迁移冒烟
- 文件：backend/tests/unit/test_migrations.py
- 关键能力：
  - 空库升级到 head。
  - Alembic 版本号与最新 head 一致。
  - ORM 全表、全列与迁移结果对账。
  - 核心唯一约束与外键存在性校验。

5. 审计链路补测
- 文件：backend/tests/integration/test_audit_logs.py
- 关键能力：草稿提交待审（match_draft_submitted）到管理员审批（match_approved）的日志链路完整性。

---

## 4. 当前非核心任务中的测试（存在但默认不跑）

1. 队员接口：backend/tests/integration/test_players.py
2. 审计日志：backend/tests/integration/test_audit_logs.py
3. 队伍核心：backend/tests/integration/test_team_core.py
4. 队伍帖子：backend/tests/integration/test_team_posts.py
5. 队伍重算：backend/tests/integration/test_team_rerate.py
6. 超管首页：backend/tests/integration/test_superadmin_home.py
7. 其他单测：test_export.py、test_chemistry.py、test_engine_internal.py、test_engine_external.py、test_app_bootstrap.py

建议：这些测试应按发布阶段分批纳入更大回归任务，而不是只在问题出现后被动运行。

---

## 5. 已落地的迁移防线

### 5.1 防线 A：核心回归强制包含迁移测试

- 任务文件：.vscode/tasks.json
- 任务：backend: run core tests
- 结果：日常回归默认会触发 migration smoke。

### 5.2 防线 B：模型与迁移结果全量对账

- 文件：backend/tests/unit/test_migrations.py
- 机制：对 Base.metadata.tables 做全表、全列对比。
- 价值：新增字段没写迁移时，测试会直接失败。

新增：

- 核心唯一约束存在性校验（如 match_event 的幂等约束）。
- 核心外键存在性校验（match_event、match_player 关键关联）。

### 5.3 防线 C：Pydantic 弃用告警升级为失败

- 文件：backend/pyproject.toml
- 配置：filterwarnings = error::pydantic.warnings.PydanticDeprecatedSince20
- 价值：消除“有 warning 但被忽略”的隐患。

---

## 6. 仍需加强的核心测试缺口

截至 2026-03-20，本章节状态如下。

### 6.1 已补齐（后端范围）

1. 迁移约束级校验
- 已补：唯一约束、外键、关键索引（team_id/match_date/expires_at/deleted_at/match_id）断言。
- 文件：backend/tests/unit/test_migrations.py

2. Alembic 驱动的集成验证路径
- 已补：新增 migration-backed integration fixture 与样例流程测试。
- 文件：backend/tests/integration/test_migration_backed_integration.py

3. 后台定时清理任务直接测试
- 已补：单次清理、循环停止、任务取消测试。
- 文件：backend/tests/unit/test_live_draft_cleanup_service.py

4. 审批与审计链路串测
- 已补：成员草稿提交待审 -> 管理员审批 -> 审计日志动作校验。
- 文件：backend/tests/integration/test_audit_logs.py

### 6.2 非后端范围状态（已建立前端基线）

1. 前端多人并发交互自动化
- 当前状态：已补最小 E2E 基线（Playwright）。
- 文件：frontend/tests/e2e/live-draft-concurrency.spec.ts
- 已覆盖：
  - 第二人进入冲突提示并跳回比赛列表。
  - 第一人正常进入实况录入页面。
  - 冲突解除后重试进入成功。
  - 同账号多标签页重入不应触发冲突拦截。
  - 第一人点击返回释放锁后，第二人可立即重新进入（relay 场景）。
- `@live` 联调场景：两阶段全流程（锁定 → 成员被拦 → owner 释放 → 成员重入）。
- 执行命令：frontend 目录下运行 `npm run test:e2e`。
- 可选联调：`npm run test:e2e:live`（需设置 `E2E_LIVE_BACKEND=1` 且本地后端已启动）。
- 后续建议：跨浏览器并发场景（Firefox / WebKit）、CI 自动化门禁落地。

---

## 7. 推荐执行命令

### 7.1 日常开发（最小安全集）

```powershell
uv run pytest tests/integration/test_matches.py tests/unit/test_migrations.py -q
```

### 7.2 核心回归（推荐合并前）

```powershell
uv run pytest tests/integration/test_auth.py tests/integration/test_matches.py tests/integration/test_rankings.py tests/integration/test_team_settings.py tests/integration/test_turnovers.py tests/integration/test_migration_backed_integration.py tests/unit/test_match_service_core.py tests/unit/test_match_service_levels.py tests/unit/test_rating_service_core.py tests/unit/test_migrations.py tests/unit/test_live_draft_cleanup_service.py -q
```

如改动审批/审计流程，追加：

```powershell
uv run pytest tests/integration/test_audit_logs.py -q
```

### 7.3 全量回归（发布前）

```powershell
uv run pytest tests/ -q
```

---

## 8. 变更类型与测试映射

1. 改动 match / match_event / rating 相关模型
- 必跑：test_matches.py + test_match_service_core.py + test_migrations.py

2. 改动权限、审批、角色逻辑
- 必跑：test_auth.py + test_players.py + test_matches.py

3. 改动团队参数与算法系数
- 必跑：test_team_settings.py + test_rating_service_core.py + test_rankings.py

4. 改动迁移脚本或新增字段
- 必跑：test_migrations.py + 至少一组相关 integration。

---

## 9. 合并前验收清单

1. 核心回归 100% 通过。
2. 无 Pydantic 弃用告警。
3. migration smoke 通过，且无 ORM/DB 列漂移。
4. 改动功能对应的集成测试至少新增 1 个正向场景和 1 个异常场景。
5. 若涉及并发/幂等，至少包含冲突路径测试。

---

## 10. 下一步落地建议

1. 在 frontend 建立 E2E 测试体系，补齐并发交互自动化。
2. 增加更多 Alembic-based integration 场景（players、audit 查询过滤、team 流程）。
3. 将发布前全量回归接入 CI 的必经门禁。
