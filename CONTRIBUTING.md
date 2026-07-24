# Contributing

Thanks for improving SolArc-Ultimate.

## Development Setup

Backend:

```bash
cd backend
uv sync
copy .env.example .env
uv run alembic upgrade head
uv run python scripts/seed_demo.py
uv run python run.py --reload
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

## Checks

Run the checks that match your change:

```bash
cd backend
uv run pytest tests/ -q
uv run ruff check app/ tests/

cd ../frontend
npm run type-check
npm run build

cd ../miniprogram
npm run type-check
```

## Data Rules

Do not commit:

- `.env` files with real values.
- Production databases or exported CSV/JSON files.
- Real player names, emails, OpenIDs, or team data.
- Domain filing materials or private deployment records.
- Third-party PDFs or assets without redistribution permission.

Use `backend/scripts/seed_demo.py` for public examples.
