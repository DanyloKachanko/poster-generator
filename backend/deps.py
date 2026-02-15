import os
from pathlib import Path
from dotenv import load_dotenv

from leonardo import LeonardoAI
from export import PosterExporter
from listing_generator import ListingGenerator
from printify import PrintifyAPI
from notifications import NotificationService
from scheduler import PublishScheduler
from etsy import EtsyAPI
from batch import BatchManager
from upscaler import UpscaleService
from presets_manager import PresetsManager
from dovshop_client import DovShopClient
from telegram_bot import TelegramBot

# Load .env from root directory (parent of backend/)
root_env = Path(__file__).parent.parent / ".env"
load_dotenv(root_env)
load_dotenv()  # Also try local .env as fallback

# API Keys
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")
if not LEONARDO_API_KEY:
    print("WARNING: LEONARDO_API_KEY not set. API calls will fail.")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Service singletons
leonardo = LeonardoAI(LEONARDO_API_KEY or "")
exporter = PosterExporter(leonardo, output_dir="./exports")
listing_gen = ListingGenerator(api_key=ANTHROPIC_API_KEY or "")
printify = PrintifyAPI()
notifier = NotificationService()
publish_scheduler = PublishScheduler(printify, notifier)
etsy = EtsyAPI()
publish_scheduler.etsy = etsy
publish_scheduler.listing_gen = listing_gen
batch_manager = BatchManager(notifier=notifier)
upscale_service = UpscaleService()
presets_manager = PresetsManager()
dovshop_client = DovShopClient()
telegram_bot = TelegramBot()
