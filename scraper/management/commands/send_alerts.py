from django.core.management.base import BaseCommand

from scraper.alert_engine import AlertEngine


class Command(BaseCommand):
    help = "Evaluate all user alert preferences and send deadline reminder emails."

    def handle(self, *args, **options):
        engine = AlertEngine()
        results = engine.run()
        self.stdout.write(self.style.SUCCESS(
            f"Alerts sent: {results['sent']}  |  Already-notified skipped: {results['skipped']}"
        ))
