"""
AlertEngine — checks upcoming tender deadlines against each user's
AlertPreference and sends reminder emails (via Django's email backend,
console-simulated when no SMTP creds are configured). Notifications for
multiple users are dispatched concurrently with `threading`.
"""

import logging
import datetime
import threading

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from mongoengine.errors import NotUniqueError

from tenders.models import AlertPreference, AlertLog, Tender

logger = logging.getLogger("scraper")
User = get_user_model()


class AlertEngine:
    """Evaluates deadline reminders for every user with alerts enabled."""

    def __init__(self, thread_count=None):
        self.thread_count = thread_count or getattr(settings, "SCRAPER_THREAD_COUNT", 4)
        self._lock = threading.Lock()
        self.sent_count = 0
        self.skipped_count = 0

    def run(self):
        preferences = list(AlertPreference.objects.filter(enabled=True))
        logger.info("AlertEngine: evaluating %d user preference(s)", len(preferences))

        threads = []
        # Simple manual thread batching (as required) rather than a pool,
        # to keep the alert-fan-out logic explicit and easy to follow.
        for batch_start in range(0, len(preferences), self.thread_count):
            batch = preferences[batch_start: batch_start + self.thread_count]
            threads = []
            for pref in batch:
                t = threading.Thread(target=self._process_user, args=(pref,), name=f"alert-{pref.user_id}")
                threads.append(t)
                t.start()
            for t in threads:
                t.join()

        return {"sent": self.sent_count, "skipped": self.skipped_count}

    def _process_user(self, pref: AlertPreference):
        try:
            user = User.objects.filter(id=pref.user_id).first()
            if not user:
                return
            email = pref.email or user.email
            if not email:
                logger.warning("User %s has alerts enabled but no email on file", pref.user_id)
                return

            candidate_tenders = self._matching_tenders(pref)
            due_tenders = [t for t in candidate_tenders if self._is_due(t, pref)]

            for tender in due_tenders:
                if self._already_notified(pref.user_id, tender.reference_no):
                    with self._lock:
                        self.skipped_count += 1
                    continue
                self._send_reminder(email, tender)
                self._log_alert(pref.user_id, tender.reference_no)
                with self._lock:
                    self.sent_count += 1
        except Exception:  # noqa: BLE001 - one user's failure shouldn't kill the batch
            logger.exception("AlertEngine failed while processing user_id=%s", pref.user_id)

    @staticmethod
    def _matching_tenders(pref: AlertPreference):
        qs = Tender.objects.filter(status__ne="closed")
        if pref.categories:
            qs = qs.filter(category__in=pref.categories)
        if pref.states:
            qs = qs.filter(state__in=pref.states)
        return list(qs)

    @staticmethod
    def _is_due(tender: Tender, pref: AlertPreference) -> bool:
        days_left = tender.days_remaining()
        return days_left in (pref.remind_days_before or [7, 3, 1])

    @staticmethod
    def _already_notified(user_id: int, reference_no: str) -> bool:
        return AlertLog.objects.filter(user_id=user_id, tender_reference_no=reference_no).first() is not None

    @staticmethod
    def _log_alert(user_id: int, reference_no: str):
        try:
            AlertLog(user_id=user_id, tender_reference_no=reference_no).save()
        except NotUniqueError:
            pass

    @staticmethod
    def _send_reminder(email: str, tender: Tender):
        days_left = tender.days_remaining()
        subject = f"⏰ Tender deadline in {days_left} day(s): {tender.title[:60]}"
        message = (
            f"Reference: {tender.reference_no}\n"
            f"Department: {tender.department}\n"
            f"Category: {tender.category}  |  State: {tender.state}\n"
            f"Estimated value: ₹{tender.estimated_value:,.0f}\n"
            f"Deadline: {tender.deadline.strftime('%d %b %Y, %H:%M')} IST\n"
            f"Source: {tender.source_portal} — {tender.source_url}\n\n"
            f"— Tender Trail Alert Engine"
        )
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            logger.info("Alert sent to %s for tender %s (%s days left)", email, tender.reference_no, days_left)
        except Exception:
            logger.exception("Failed to send alert email to %s for %s", email, tender.reference_no)
