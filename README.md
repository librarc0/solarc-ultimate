# SolArc-Ultimate

SolArc-Ultimate 是一个开源的飞盘队伍管理与战力评分系统，提供队伍成员管理、比赛录入、球员评分、排行榜、赛程和微信小程序端。它的核心目标是帮助飞盘队伍把原本分散在表格、群消息和人工经验里的数据，整理成一个可自部署、可二次开发的系统。

English summary: SolArc-Ultimate is an open-source ultimate frisbee team management and rating system with match entry, player ratings, rankings, team workflows, and a lightweight mini-program client.

## 适用场景

主要场景是极限飞盘：

- 队内训练赛、内战、分组和出勤管理。
- 对外比赛记录、对手强度校准和赛后复盘。
- 球员 `mu`、`sigma`、保守战力、进攻/防守/默契等多维排行榜。
- 队长、管理员、普通队员的多角色协作。

它也可以改造成其他需要“多人对抗 + 数据录入 + 动态评分”的场景，例如篮球/足球/羽毛球双打、电竞战队、桌游/棋类联赛、企业内部训练赛、销售团队竞赛、辩论/答辩评分等。飞盘业务字段是第一版默认体验，核心评分引擎已经尽量保持独立，方便迁移到其他领域。

## 功能概览

- 账号注册、登录、队伍创建、成员审批和角色权限。
- 内战/外战比赛录入，支持比分级、进球/助攻级、完整技术统计级数据。
- OpenSkill / Weng-Lin 风格评分，输出 `mu`、`sigma`、保守战力和历史变化。
- 排行榜：综合战力、稳定性、进球、助攻、防守、默契等。
- 赛程、出勤、分 line/阵容辅助。
- Vue Web 前端，适合移动端比赛日录入。
- uni-app 微信小程序端，适合轻量移动访问。
- Docker Compose 自部署，默认使用 SQLite。
- 虚构 demo 队伍和 demo 比赛数据，开箱即可体验。

## 技术栈

- Backend: FastAPI, SQLAlchemy async, Alembic, Pydantic, OpenSkill, SQLite.
- Web frontend: Vue 3, Vite, Pinia, Vant, ECharts.
- Mini-program: uni-app, Vue, Pinia.
- Tooling: uv, npm, Docker Compose, pytest, ruff, GitHub Actions.

## 最快体验：Docker

准备环境：

- Docker / Docker Compose
- Git

启动：

```bash
git clone https://github.com/librarc0/solarc-ultimate.git
cd solarc-ultimate
copy .env.example .env
docker compose up --build -d
docker compose exec backend python scripts/seed_demo.py
```

打开：

```text
http://localhost:8080
```

后端容器启动时会自动执行数据库迁移。`seed_demo.py` 只写入虚构数据；如果 demo 队伍已存在，会自动跳过，不会重复污染数据。

## 本地开发运行

准备环境：

- Python 3.11
- uv
- Node.js 20/22
- npm

后端：

```bash
cd backend
uv sync --all-extras --dev
copy .env.example .env
uv run alembic upgrade head
uv run python scripts/seed_demo.py
uv run python run.py --host 0.0.0.0 --port 8000 --reload
```

Web 前端：

```bash
cd frontend
npm ci
npm run dev
```

默认访问：

```text
http://localhost:5173
```

小程序：

```bash
cd miniprogram
npm ci
npm run dev:mp-weixin
```

然后使用微信开发者工具导入 `miniprogram` 项目。公开版默认使用占位 AppID 和本地 API 地址，正式发布前需要配置自己的微信小程序 AppID、HTTPS API 域名和 `.env.production`。

## Demo 账号

| Username | Password | Role |
| --- | --- | --- |
| `demo_owner` | `Demo@123456` | 队伍 owner |
| `demo_admin` | `Demo@123456` | 队伍 admin |
| `demo_ace` | `Demo@123456` | 队员 |
| `demo_handler` | `Demo@123456` | 队员 |

建议体验路径：

1. 用 `demo_owner` 登录。
2. 进入排行榜，查看不同球员的 `mu`、`sigma` 和保守战力。
3. 查看历史比赛，理解内战、外战、Level 1/2/3 数据的差异。
4. 新增一场比赛，再回到排行榜观察评分变化。
5. 查看球员详情和评分历史，确认每场比赛如何影响个人战力。

更多 demo 说明见 `docs/demo-data.md`。

## 核心评分引擎

评分核心在 `backend/app/rating_engine`。它使用纯 dataclass 输入输出，不依赖 FastAPI、SQLAlchemy 或数据库，适合单独复用。

命令行示例：

```bash
cd backend
uv run python scripts/rating_cli.py examples/rating_match.json
```

输出会包含每个参与者的：

- `mu_before` / `mu_after`
- `sigma_before` / `sigma_after`
- `conservative_before` / `conservative_after`
- `delta_mu`

说明：

- 本项目依赖 MIT 许可证的 `openskill` 包。
- 公开文档统一使用 “OpenSkill / Weng-Lin style rating” 表述。
- 不把本项目描述为 Microsoft TrueSkill 的实现。

算法模块更详细的最小用法见 `backend/app/rating_engine/README.md`。

## 如何改造成其他项目

如果你想把它用于飞盘以外的场景，建议从这几层开始改：

- 术语层：把“球员、队伍、比赛、进球、助攻、防守”等前端文案替换成你的业务术语。
- 数据层：保留 match/player/rating 的主线，调整统计字段，例如得分、回合、任务完成数、胜负结果。
- 评分层：优先复用 `backend/app/rating_engine`，只替换输入权重和数据解释。
- 展示层：排行榜、个人详情、历史记录通常可以保留，只需要换指标名称。

第一版没有拆成独立 PyPI 包。如果你只需要算法，可以直接复制 `backend/app/rating_engine` 和 `backend/scripts/rating_cli.py` 作为起点。

## 测试与质量检查

后端：

```bash
cd backend
uv run pytest tests/ -q
uv run ruff check app/ tests/
```

前端：

```bash
cd frontend
npm ci
npm run type-check
npm run build
```

小程序：

```bash
cd miniprogram
npm ci
npm run type-check
npm run build:mp-weixin
```

Docker 配置检查：

```bash
docker compose config
```

## 目录结构

```text
backend/                  FastAPI 后端、数据库模型、评分服务、测试
backend/app/rating_engine  可独立复用的评分核心
backend/scripts/           demo seed、评分 CLI、schema 检查脚本
frontend/                 Vue Web 前端
miniprogram/              uni-app 微信小程序
docs/                     demo 数据和开发说明
specs/                    产品规格和接口说明
docker-compose.yml        本地/服务器自部署入口
```

## 安全说明

公开仓库不包含生产凭据、真实球员数据、真实导出文件、备案材料、私有部署日志或真实 `.env` 文件。

部署自己的实例前：

- 生成新的 `SECRET_KEY`。
- 只在 `.env` 或运行环境变量里配置 SMTP、微信小程序和部署密钥。
- 不要提交 `.env`、数据库、导出 CSV/JSON、压缩包或真实队伍数据。
- 任何曾经进入 Git 历史的密钥都应立即轮换。

## License

MIT. See `LICENSE`.
