# Poster Generator

## Commands
- `docker-compose up --build` — start all services (backend :8001, frontend :3001, db :5432)
- `docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml up --build` — dev mode with hot-reload
- Backend only: `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
- Frontend only: `cd frontend && npm run dev`

## Architecture
- Backend: FastAPI (`backend/main.py`), routes in `backend/routes/` (20 modules)
- Frontend: Next.js 14 (`frontend/app/`), Tailwind CSS
- DB: PostgreSQL + asyncpg, soft-delete via `archived` column
- Config: `backend/config.py` (models, sizes, presets), `backend/deps.py` (service singletons)
- Key service modules: `leonardo.py`, `printify.py`, `etsy.py`, `listing_generator.py`, `scheduler.py`

## Environment
- `.env` in project root (not in backend/ or frontend/)
- Required: LEONARDO_API_KEY, ANTHROPIC_API_KEY, PRINTIFY_API_TOKEN, PRINTIFY_SHOP_ID, DATABASE_URL
- Optional: ETSY_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DOVSHOP_API_KEY, DOVSHOP_API_URL

## Gotchas
- Leonardo: dimensions must be multiples of 8, max 1536; `null` API fields → use `or 0`
- Printify: Provider 99, Blueprint 282; POST ignores tags → PUT after; scale factors in `backend/sizes.py`
- Claude JSON: `json.loads(content, strict=False)` for control chars
- Docker: use `docker-compose` (not `docker compose`)
