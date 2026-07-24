# EaglesPower 快速启动指南

**面向**: 队伍管理员（首次部署）
**环境要求**: 安装了 Docker & Docker Compose 的 NAS 或本地电脑

---

## 一、NAS 部署（推荐）

### 1. 将项目文件复制到 NAS

```bash
# 方式 A: 通过 SSH
ssh admin@nas-ip
cd /volume1/docker
git clone <仓库地址> eaglespower
cd eaglespower

# 方式 B: 通过文件管理器（SMB/NFS）
# 将整个项目文件夹上传到 NAS 的 docker 共享目录
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`，**至少修改以下内容**：

```env
# 必改：JWT 密钥（随机字符串，越长越好）
SECRET_KEY=请替换为随机字符串至少32位

# 可选：修改数据库路径（默认使用 SQLite）
DATABASE_URL=sqlite+aiosqlite:////data/eaglespower.db

# 可选：数据库文件存储路径（挂载卷）
DATA_PATH=/data
```

> ⚠️ 若使用 PostgreSQL，将 `DATABASE_URL` 改为：
> `postgresql+asyncpg://user:password@postgres:5432/eaglespower`

### 3. 启动服务

```bash
docker compose up -d
```

**群晖 Container Manager 用户**：
1. 打开 Container Manager → 项目
2. 点击"从路径创建" → 选择 `eaglespower` 文件夹
3. 点击"构建并启动"

### 4. 验证服务启动

```bash
# 查看容器状态
docker compose ps

# 预期输出：
# backend   running   0.0.0.0:8000->8000/tcp
# frontend  running   0.0.0.0:8080->8080/tcp

# 健康检查
curl http://localhost:8080/health
# 应返回：{"code":0,"data":{"status":"ok"},"message":""}
```

### 5. 从手机访问

确保手机和 NAS 在同一 WiFi 下，打开浏览器访问：

```
http://NAS内网IP:8080
# 例如: http://192.168.1.100:8080
```

> **提示**: 群晖用户可在"控制面板 → 网络 → 网络接口"查看内网 IP

---

## 二、首次使用：创建队伍与管理员账号

1. 打开浏览器访问系统，自动跳转到注册页
2. 填写账号（6-20 位字母数字）和密码（≥8 位）
3. 填写「队伍名称」（首个注册用户专属字段）
4. 提交后，**第一个注册的用户自动成为队伍 Owner**，无需审批
5. 登录后进入"管理员"界面，开始邀请队员注册

---

## 三、邀请队员加入

1. 将系统访问地址（如 `http://192.168.1.100:8080`）发送给队员
2. 队员注册后状态为 `pending`（待审批）
3. 管理员登录 → 底部「我的」→「管理」→「待审批成员」→ 点击批准

---

## 四、录入第一场比赛

1. 管理员登录
2. 点击底部导航「+」按钮
3. 选择「内战」→ 分配 A/B 队阵容（各队至少 3 人）
4. 点击「开始比赛」→ 比赛计时开始
5. 点击「A队得分」/「B队得分」录入进球
6. 比赛结束后点击「结束比赛」→「提交」
7. 评分自动计算，排行榜更新

---

## 五、本地开发环境

### 后端

```bash
cd backend
# 安装 uv（Python 包管理器）
pip install uv

# 安装依赖
uv sync

# 创建 .env
cp .env.example .env

# 运行数据库迁移
uv run alembic upgrade head

# 启动开发服务器
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 访问: http://localhost:5173
```

---

## 六、Docker Compose 文件说明

```yaml
# docker-compose.yml 关键配置
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"      # 后端 API（可不对外暴露，仅内部）
    volumes:
      - eaglespower_data:/data  # SQLite 数据持久化
    env_file:
      - ./backend/.env

  frontend:
    build: ./frontend
    ports:
      - "8080:80"        # 对外唯一端口（Nginx）
    depends_on:
      - backend

volumes:
  eaglespower_data:      # 命名卷，群晖路径: /volume1/docker/volumes/eaglespower_data/
```

---

## 七、常见问题

**Q: 手机上图片/界面显示不正常？**
A: 确保手机和 NAS 在同一 WiFi，用内网 IP 访问（不要用 localhost）。

**Q: 忘记管理员密码怎么办？**
A: 暂无前端找回功能。可通过 `docker exec` 进入 backend 容器，使用 SQLite 命令直接修改 password_hash：
```bash
docker exec -it eaglespower-backend-1 python -c "
from passlib.hash import bcrypt; print(bcrypt.hash('新密码'))
"
# 然后用 SQLite CLI 更新 password_hash 字段
```

**Q: 如何备份数据？**
A: 备份 Docker 数据卷即可。群晖用户可在 Hyper Backup 中添加 `/volume1/docker/volumes/eaglespower_data/` 路径。

**Q: 如何升级到新版本？**
A: 
```bash
git pull
docker compose down
docker compose up -d --build
# 新版本启动时自动运行 alembic upgrade head
```

**Q: 如何切换到 PostgreSQL？**
A: 修改 `backend/.env` 中 `DATABASE_URL`，并在 `docker-compose.yml` 中添加 PostgreSQL 服务，重新部署。
