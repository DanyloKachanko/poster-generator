"""
SEO Auto-Refresh Scheduler

Runs on a configurable schedule (default: every 3 days).
Each run:
1. Finds listings with expired autocomplete cache (>7 days old)
2. Re-validates their tags against Etsy search volume
3. If score dropped below threshold → logs for regeneration
4. Logs everything to seo_refresh_log

Keeps listings' tag validation fresh so the SEO editor
always shows accurate data.
"""

import asyncio
import logging
import time
from typing import Optional

import database as db

logger = logging.getLogger(__name__)


class SEOScheduler:
    MIN_ETSY_SCORE = 0.8       # Flag listings below this
    MAX_PER_RUN = 15           # Don't overwhelm Etsy API per run

    def __init__(self, etsy_api, etsy_validator):
        self._etsy = etsy_api
        self._validator = etsy_validator
        self._running = False

    async def run(self) -> dict:
        """Main scheduler entry point. Returns a summary of the run."""
        if self._running:
            return {"status": "already_running"}

        self._running = True
        logger.info("SEO scheduler: starting run")

        try:
            # Get Etsy tokens
            tokens = await db.get_etsy_tokens()
            if not tokens or not tokens.get("shop_id"):
                return {"status": "error", "detail": "Etsy not connected"}

            access_token = tokens["access_token"]
            if tokens["expires_at"] < int(time.time()):
                new_tokens = await self._etsy.refresh_access_token(tokens["refresh_token"])
                await db.save_etsy_tokens(
                    access_token=new_tokens.access_token,
                    refresh_token=new_tokens.refresh_token,
                    expires_at=new_tokens.expires_at,
                )
                access_token = new_tokens.access_token

            # Fetch all listings
            listings = await self._etsy.get_all_listings(access_token, tokens["shop_id"])

            revalidated = 0
            flagged = []

            for listing in listings:
                if revalidated >= self.MAX_PER_RUN:
                    break

                tags = listing.get("tags", [])
                if not tags:
                    continue

                # Check if any tags need revalidation (not in cache or expired)
                needs_check = False
                for tag in tags:
                    try:
                        cached = await db.get_cached_tag(tag.lower().strip(), "etsy")
                        if not cached:
                            needs_check = True
                            break
                    except Exception:
                        needs_check = True
                        break

                if not needs_check:
                    continue

                # Re-validate
                result = await self._validator.check_tags(tags)
                revalidated += 1

                if result["score"] < self.MIN_ETSY_SCORE:
                    listing_info = {
                        "listing_id": listing.get("listing_id"),
                        "title": listing.get("title", ""),
                        "etsy_score": result["score"],
                        "dead_tags": [r["tag"] for r in result["results"] if not r["found"]],
                    }
                    flagged.append(listing_info)
                    logger.info(
                        f"SEO scheduler: flagged listing {listing_info['listing_id']} "
                        f"(score={result['score']:.0%}, dead={len(listing_info['dead_tags'])} tags)"
                    )

            # Clean expired cache entries
            await db.clear_expired_cache()

            summary = {
                "status": "ok",
                "total_listings": len(listings),
                "revalidated": revalidated,
                "flagged": len(flagged),
                "flagged_listings": flagged,
            }

            logger.info(
                f"SEO scheduler: done. Revalidated {revalidated}, flagged {len(flagged)}"
            )
            return summary

        except Exception as e:
            logger.error(f"SEO scheduler error: {e}")
            return {"status": "error", "detail": str(e)}
        finally:
            self._running = False
