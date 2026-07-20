"""
PortalCoordinator — runs every registered scraper concurrently using
concurrent.futures.ThreadPoolExecutor, so a slow/unreachable portal never
blocks the others. Each thread's failures are isolated by BaseScraper's own
try/except, so this layer just focuses on fan-out/fan-in and de-duplication.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings
from mongoengine.errors import NotUniqueError

from .parser import TenderParser
from .scrapers import get_default_scrapers
from tenders.models import Tender

logger = logging.getLogger("scraper")

_save_lock = threading.Lock()  # guards the "check-then-save" upsert below


def _run_one_scraper(scraper):
    """Executed in a worker thread: fetch raw records, return normalized ones."""
    thread_name = threading.current_thread().name
    logger.info("[%s] Starting scrape: %s", thread_name, scraper.portal_name)
    raw_records = scraper.fetch()
    normalized = [TenderParser.normalize(r) for r in raw_records]
    normalized = [n for n in normalized if n is not None]
    logger.info(
        "[%s] %s produced %d normalized tenders", thread_name, scraper.portal_name, len(normalized)
    )
    return normalized


def _upsert_tender(record: dict) -> str:
    """
    Insert a new tender or update an existing one by reference_no.
    Returns "created", "updated", or "skipped".
    """
    with _save_lock:
        existing = Tender.objects(reference_no=record["reference_no"]).first()
        if existing:
            for key, value in record.items():
                setattr(existing, key, value)
            existing.save()
            existing.refresh_status()
            return "updated"
        try:
            tender = Tender(**record)
            tender.save()
            tender.refresh_status()
            return "created"
        except NotUniqueError:
            return "skipped"


class PortalCoordinator:
    """Fans out scraping across all configured portals using a thread pool."""

    def __init__(self, scrapers=None, max_workers=None):
        self.scrapers = scrapers or get_default_scrapers()
        self.max_workers = max_workers or getattr(settings, "SCRAPER_THREAD_COUNT", 4)

    def run(self):
        results = {"created": 0, "updated": 0, "skipped": 0, "portals_run": 0, "errors": []}

        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="scraper") as pool:
            future_to_scraper = {
                pool.submit(_run_one_scraper, scraper): scraper for scraper in self.scrapers
            }
            for future in as_completed(future_to_scraper):
                scraper = future_to_scraper[future]
                try:
                    normalized_records = future.result()
                except Exception as exc:  # noqa: BLE001 - isolate one bad portal
                    logger.exception("Portal %s failed entirely: %s", scraper.portal_name, exc)
                    results["errors"].append(f"{scraper.portal_name}: {exc}")
                    continue

                results["portals_run"] += 1
                for record in normalized_records:
                    outcome = _upsert_tender(record)
                    results[outcome] = results.get(outcome, 0) + 1

        logger.info("Scrape run complete: %s", results)
        return results
