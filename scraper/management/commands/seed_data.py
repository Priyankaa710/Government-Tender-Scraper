from django.core.management.base import BaseCommand

from scraper.parser import TenderParser
from scraper.scrapers import _generate_sample_batch
from tenders.models import Tender


class Command(BaseCommand):
    help = "Seed MongoDB with sample tender data for demos/testing (no network calls)."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=40, help="Number of sample tenders to create")
        parser.add_argument("--flush", action="store_true", help="Delete all existing tenders first")

    def handle(self, *args, **options):
        if options["flush"]:
            deleted = Tender.objects.count()
            Tender.objects.delete()
            self.stdout.write(self.style.WARNING(f"Flushed {deleted} existing tenders."))

        raw = _generate_sample_batch(
            "Sample Seed Data", "https://data.gov.in", count=options["count"]
        )
        created = 0
        for r in raw:
            normalized = TenderParser.normalize(r)
            if not normalized:
                continue
            if Tender.objects(reference_no=normalized["reference_no"]).first():
                continue
            tender = Tender(**normalized)
            tender.save()
            tender.refresh_status()
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created} sample tenders."))
