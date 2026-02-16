from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from deps import publish_scheduler, telegram_bot
from auth import REQUIRE_AUTH, verify_token
import database as db

from routes.auth_routes import router as auth_router
from routes.generation import router as generation_router
from routes.export import router as export_router
from routes.listings import router as listings_router
from routes.printify_routes import router as printify_router
from routes.presets import router as presets_router
from routes.analytics import router as analytics_router
from routes.etsy_routes import router as etsy_router
from routes.dpi import router as dpi_router
from routes.library import router as library_router
from routes.batch import router as batch_router
from routes.pipeline import router as pipeline_router
from routes.schedule import router as schedule_router
from routes.calendar import router as calendar_router
from routes.mockups import router as mockups_router
from routes.competitors import router as competitors_router
from routes.products import router as products_router
from routes.custom_presets import router as custom_presets_router
from routes.dovshop import router as dovshop_router
from routes.sync_etsy import router as sync_router
from routes.sync_ui import router as sync_ui_router

# Paths that don't require auth
_PUBLIC_PATHS = {"/auth/login", "/health", "/docs", "/openapi.json", "/redoc"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not REQUIRE_AUTH:
            return await call_next(request)

        path = request.url.path
        if path in _PUBLIC_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        # Allow Etsy OAuth callback
        if path.startswith("/etsy/callback"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        token = auth_header[7:]
        if not verify_token(token):
            return JSONResponse({"detail": "Invalid or expired token"}, status_code=401)

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and scheduler on startup."""
    import os
    scheduler_enabled = os.getenv("SCHEDULER_ENABLED", "true").lower() in ("true", "1", "yes")

    await db.init_db()
    if scheduler_enabled:
        await publish_scheduler.start()
        await telegram_bot.start()
    yield
    if scheduler_enabled:
        await telegram_bot.stop()
        await publish_scheduler.stop()


app = FastAPI(title="Poster Generator API", version="1.0.0", lifespan=lifespan)

# Auth middleware (before CORS so 401 responses get CORS headers)
app.add_middleware(AuthMiddleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all route modules
app.include_router(auth_router)
app.include_router(generation_router)
app.include_router(export_router)
app.include_router(listings_router)
app.include_router(printify_router)
app.include_router(presets_router)
app.include_router(analytics_router)
app.include_router(etsy_router)
app.include_router(dpi_router)
app.include_router(library_router)
app.include_router(batch_router)
app.include_router(pipeline_router)
app.include_router(schedule_router)
app.include_router(calendar_router)
app.include_router(mockups_router)
app.include_router(competitors_router)
app.include_router(products_router)
app.include_router(custom_presets_router)
app.include_router(dovshop_router)
app.include_router(sync_router)
app.include_router(sync_ui_router)
