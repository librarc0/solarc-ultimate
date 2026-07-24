# Changelog

## v0.9.8-open-source.1

首个脱敏开源版本。该版本用于公开评估、二次开发和自部署体验，不包含线上生产配置、真实队伍数据、真实导出文件、备案材料或私有部署记录。

### 包含内容

- FastAPI 后端、Alembic 迁移、SQLite 默认配置。
- Vue Web 前端。
- uni-app 微信小程序源码。
- Docker Compose 自部署配置。
- 虚构 demo 队伍 `demo_mix`、10 名虚构球员和 6 场虚构比赛。
- 独立评分核心 `backend/app/rating_engine`。
- 评分 CLI 示例 `backend/scripts/rating_cli.py`。
- 后端、前端、小程序测试与构建说明。
- MIT License、Security、Contributing、Notice 文档。

### Docker 部署

最短体验流程：

```bash
git clone https://github.com/librarc0/solarc-ultimate.git
cd solarc-ultimate
copy .env.example .env
docker compose up --build -d
docker compose exec backend python scripts/seed_demo.py
```

访问：

```text
http://localhost:8080
```

生产部署前必须修改：

- `.env` 中的 `SECRET_KEY`
- `ALLOWED_ORIGINS`
- `APP_BASE_URL`
- 如需邮件找回密码，配置 SMTP
- 如需微信登录，配置 `WX_APP_ID` 和 `WX_APP_SECRET`
- 如需公网访问，配置自己的 HTTPS 域名和反向代理

### Demo 账号

| Username | Password | Role |
| --- | --- | --- |
| `demo_owner` | `Demo@123456` | 队伍 owner |
| `demo_admin` | `Demo@123456` | 队伍 admin |
| `demo_ace` | `Demo@123456` | 队员 |
| `demo_handler` | `Demo@123456` | 队员 |

### 验证状态

发布前已在本地验证：

- 后端测试：`383 passed, 7 skipped`
- 后端 lint：`ruff check app/ tests/`
- 前端：`npm run type-check`、`npm run build`
- 小程序：`npm run type-check`、`npm run build:mp-weixin`
- Docker Compose 配置：`docker compose config`

`docker compose build` 需要本机 Docker daemon 正常运行。
