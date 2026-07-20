import logging
import time

from django.core.management.base import BaseCommand

from scraper.threading_utils import PortalCoordinator

logger = logging.getLogger("scraper")


class Command(BaseCommand):
    help = "Fetch tenders from all configured government portals (multi-threaded)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Keep running forever, sleeping SCRAPER_INTERVAL_HOURS between runs.",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        coordinator = PortalCoordinator()

        while True:
            self.stdout.write(self.style.NOTICE("Starting scraper run across all portals..."))
            results = coordinator.run()
            self.stdout.write(self.style.SUCCESS(
                f"Done. Created={results['created']} Updated={results['updated']} "
                f"Skipped={results['skipped']} PortalsRun={results['portals_run']} "
                f"Errors={len(results['errors'])}"
            ))
            for err in results["errors"]:
                self.stdout.write(self.style.WARNING(f"  ! {err}"))

            if not options["loop"]:
                break

            sleep_seconds = settings.SCRAPER_INTERVAL_HOURS * 3600
            self.stdout.write(f"Sleeping {settings.SCRAPER_INTERVAL_HOURS}h until next run...")
            time.sleep(sleep_seconds)
