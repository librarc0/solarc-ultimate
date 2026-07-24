# EAGLESPOWER 后端测试速查（一页版）

## 1. 何时跑什么

1. 日常改动（最小安全集）
```powershell
uv run pytest tests/integration/test_matches.py tests/unit/test_migrations.py -q
```

2. 合并前（核心回归）
```powershell
uv run pytest tests/integration/test_auth.py tests/integration/test_matches.py tests/integration/test_rankings.py tests/integration/test_team_settings.py tests/integration/test_turnovers.py tests/unit/test_match_service_core.py tests/unit/test_match_service_levels.py tests/unit/test_rating_service_core.py tests/unit/test_rating_adjustments.py tests/unit/test_migrations.py -q
```

3. 发布前（全量）
```powershell
uv run pytest tests/ -q
```

---

## 2. 关键门禁（必须通过）

1. 迁移门禁
- `tests/unit/test_migrations.py` 必须通过。
- 该测试会验证：
  - Alembic 空库升级到 head。
  - ORM 表/列与迁移后数据库对齐。
  - 核心唯一约束与外键存在。

2. 告警门禁
- Pydantic V2 弃用警告视为失败。
- 配置位置：`backend/pyproject.toml`。

3. 并发门禁
- 实况草稿并发与锁相关改动，必须覆盖：
  - 抢锁成功路径
  - 第二人冲突路径
  - 保存释放后可见路径

---

## 3. 变更类型对照

1. 改 match/match_event/rating
- 跑：`test_matches.py` + `test_match_service_core.py` + `test_migrations.py`

2. 改权限/审批/角色
- 跑：`test_auth.py` + `test_players.py` + `test_matches.py`

3. 改队伍参数/算法
- 跑：`test_team_settings.py` + `test_rating_service_core.py` + `test_rating_adjustments.py` + `test_rankings.py`

4. 改模型/迁移脚本
- 跑：`test_migrations.py` + 至少 1 组相关 integration

---

## 4. 常见失败与处理

1. `match` 或 `match_event` 字段缺失
- 先检查是否漏了 Alembic migration。
- 跑 `uv run alembic upgrade head` 后重测。

2. 新增字段后集成测试通过但线上迁移失败
- 说明测试走了 `create_all` 路径，未覆盖真实迁移。
- 先补 migration test 断言，再补 Alembic-based integration。

3. 出现 PydanticDeprecatedSince20
- 立即修代码，不要忽略 warning。

---

## 5. 推荐执行顺序

1. 写功能/修复。
2. 先跑最小安全集。
3. 通过后跑核心回归。
4. 合并前确保无 warning、无迁移漂移。
5. 发布前跑全量。
