import logging
import os
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

from integrations.leonardo.client import LeonardoAI
from export import PosterExporter
from core.seo.generator import ListingGenerator
from integrations.printify.client import PrintifyAPI
from integrations.telegram.notifications import NotificationService
from scheduler import PublishScheduler
from integrations.etsy.client import EtsyAPI
from batch import BatchManager
from upscaler import UpscaleService
from presets_manager import PresetsManager
from integrations.dovshop.client import DovShopClient
from integrations.telegram.bot import TelegramBot
from integrations.etsy.sync import EtsySyncService
from integrations.pinterest.client import PinterestAPI
from integrations.pinterest.generator import PinterestPinGenerator
from integrations.pinterest.scheduler import PinterestScheduler

# Load .env from root directory (parent of backend/)
root_env = Path(__file__).parent.parent / ".env"
load_dotenv(root_env)
load_dotenv()  # Also try local .env as fallback

# API Keys
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")
if not LEONARDO_API_KEY:
    logger.warning("LEONARDO_API_KEY not set. API calls will fail.")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Service singletons
leonardo = LeonardoAI(LEONARDO_API_KEY or "")
exporter = PosterExporter(leonardo, output_dir="./exports")
listing_gen = ListingGenerator(api_key=ANTHROPIC_API_KEY or "")
printify = PrintifyAPI()
notifier = NotificationService()
etsy = EtsyAPI()
etsy_sync = EtsySyncService(etsy, printify)
publish_scheduler = PublishScheduler(
    printify=printify,
    notifier=notifier,
    etsy=etsy,
    listing_gen=listing_gen,
    etsy_sync=etsy_sync,
)
batch_manager = BatchManager(notifier=notifier)
upscale_service = UpscaleService()
presets_manager = PresetsManager()
dovshop_client = DovShopClient()
telegram_bot = TelegramBot()
pinterest_api = PinterestAPI()
pinterest_generator = PinterestPinGenerator()
pinterest_scheduler = PinterestScheduler(pinterest_api, notifier)
