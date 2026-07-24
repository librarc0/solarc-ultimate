# Deployment Guide

This guide covers the supported deployment paths for SolArc-Ultimate.

## Option 1: Build Locally With Docker Compose

Use this when you want to build images from source on your own machine or server.

```bash
git clone https://github.com/librarc0/solarc-ultimate.git
cd solarc-ultimate
copy .env.example .env
docker compose up --build -d
docker compose exec backend python scripts/seed_demo.py
```

Open:

```text
http://localhost:8080
```

The backend container runs Alembic migrations on startup. The demo seed is
separate so production databases are not seeded accidentally.

## Option 2: Use Release Images From GHCR

Release tags build Docker images and publish them to GitHub Container Registry:

```text
ghcr.io/librarc0/solarc-ultimate-backend:<tag>
ghcr.io/librarc0/solarc-ultimate-frontend:<tag>
```

Example:

```bash
copy .env.example .env
set SOLARC_VERSION=v0.9.8-open-source.2
docker compose -f docker-compose.images.yml up -d
docker compose -f docker-compose.images.yml exec backend python scripts/seed_demo.py
```

For PowerShell:

```powershell
Copy-Item .env.example .env
$env:SOLARC_VERSION = "v0.9.8-open-source.2"
docker compose -f docker-compose.images.yml up -d
docker compose -f docker-compose.images.yml exec backend python scripts/seed_demo.py
```

## Option 3: Manual Development Runtime

Backend:

```bash
cd backend
uv sync --all-extras --dev
copy .env.example .env
uv run alembic upgrade head
uv run python scripts/seed_demo.py
uv run python run.py --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Mini-program:

```bash
cd miniprogram
npm ci
npm run dev:mp-weixin
```

## Production Checklist

- Replace `SECRET_KEY` with a unique random value.
- Set `ALLOWED_ORIGINS` to your real web origin.
- Set `APP_BASE_URL` to your public HTTPS URL.
- Configure SMTP only if password reset by email is required.
- Configure `WX_APP_ID` and `WX_APP_SECRET` only if WeChat login is required.
- Put HTTPS and domain routing in a reverse proxy in front of the frontend
  container.
- Back up the Docker volume `solarc_data`.
- Do not seed demo data in production.

## Backup

The default Docker deployment stores SQLite data in the `solarc_data` named
volume. Back up that volume before upgrades:

```bash
docker run --rm -v solarc-ultimate_solarc_data:/data -v %cd%:/backup alpine tar czf /backup/solarc-data-backup.tgz -C /data .
```

On Linux/macOS:

```bash
docker run --rm -v solarc-ultimate_solarc_data:/data -v "$PWD:/backup" alpine tar czf /backup/solarc-data-backup.tgz -C /data .
```

## Upgrade

For source builds:

```bash
git pull
docker compose up --build -d
```

For release images:

```bash
set SOLARC_VERSION=<new-tag>
docker compose -f docker-compose.images.yml pull
docker compose -f docker-compose.images.yml up -d
```

The backend entrypoint runs database migrations during startup.
