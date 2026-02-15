from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from deps import publish_scheduler, telegram_bot
import database as db

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and scheduler on startup."""
    await db.init_db()
    await publish_scheduler.start()
    await telegram_bot.start()
    yield
    await telegram_bot.stop()
    await publish_scheduler.stop()


app = FastAPI(title="Poster Generator API", version="1.0.0", lifespan=lifespan)

# CORS configuration - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all route modules
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
