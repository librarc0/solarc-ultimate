# SolArc-Ultimate

SolArc-Ultimate is an open-source ultimate frisbee team management and rating
system with match entry, player ratings, rankings, team membership workflows,
and a lightweight WeChat mini-program client.

The project is built for clubs that want to replace spreadsheets with a small
self-hosted system. It combines team match results, player statistics, and an
OpenSkill / Weng-Lin style rating model to maintain player skill estimates and
leaderboards.

## Features

- Team registration, login, role-based team administration, and member approval.
- Internal and external match entry with score-only and full-stat workflows.
- Player ratings with `mu`, `sigma`, conservative score, and rating history.
- Rankings for conservative score, stability, goals, assists, defense, and chemistry.
- Web frontend optimized for mobile match-day use.
- uni-app WeChat mini-program client for lightweight mobile access.
- Docker Compose deployment with SQLite by default.
- Demo seed data for exploring the product without real team data.

## Tech Stack

- Backend: FastAPI, SQLAlchemy async, Alembic, Pydantic, OpenSkill, SQLite.
- Web frontend: Vue 3, Vite, Pinia, Vant, ECharts.
- Mini-program: uni-app, Vue, Pinia.
- Tooling: uv, npm, Docker Compose, pytest, ruff, GitHub Actions.

## Quick Start

Backend:

```bash
cd backend
uv sync
copy .env.example .env
uv run alembic upgrade head
uv run python scripts/seed_demo.py
uv run python run.py --host 0.0.0.0 --port 8000 --reload
```

Web frontend:

```bash
cd frontend
npm ci
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`.

Demo accounts:

| Username | Password | Role |
| --- | --- | --- |
| `demo_owner` | `Demo@123456` | Team owner |
| `demo_admin` | `Demo@123456` | Team admin |
| `demo_ace` | `Demo@123456` | Member |
| `demo_handler` | `Demo@123456` | Member |

Try this flow:

1. Log in as `demo_owner`.
2. Open rankings and inspect the demo ratings.
3. Open match history and view the seeded internal/external matches.
4. Submit another match and check how player `mu`, `sigma`, and conservative score change.

## Docker

Create `.env` from `.env.example`, then run:

```bash
docker compose up --build
```

The web app is exposed on `http://localhost:8080`. The backend is internal to
the compose network and proxied by the frontend container.

## Rating Engine

The reusable rating core lives in `backend/app/rating_engine`. It uses plain
dataclasses and can run without the web application or database.

CLI example:

```bash
cd backend
uv run python scripts/rating_cli.py examples/rating_match.json
```

The project depends on the MIT-licensed `openskill` package. Public docs use
"OpenSkill / Weng-Lin style rating" wording and do not describe this as a
Microsoft TrueSkill implementation.

## Tests

Backend:

```bash
cd backend
uv run pytest tests/ -q
uv run ruff check app/ tests/
```

Frontend:

```bash
cd frontend
npm ci
npm run type-check
npm run build
```

Mini-program:

```bash
cd miniprogram
npm ci
npm run type-check
npm run build:mp-weixin
```

## Security

This repository intentionally ships no production credentials, real player
exports, domain filing documents, private deployment logs, or real `.env` files.

Before deploying your own instance:

- Generate a new `SECRET_KEY`.
- Configure SMTP and mini-program credentials only in `.env`.
- Do not commit `.env`, databases, exports, or packaged archives.
- Rotate any credential that was ever committed to a private or public repo.

## License

MIT. See `LICENSE`.
