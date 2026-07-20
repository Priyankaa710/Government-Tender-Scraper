"""
MongoEngine documents backing Tender Trail.

Tenders live entirely in MongoDB. Django's relational auth user (see
users.models / django.contrib.auth.User) is referenced here only by its
integer primary key (``user_id``), since MongoEngine documents cannot
hold a foreign key into a SQL table.
"""

import datetime

from mongoengine import (
    Document,
    StringField,
    FloatField,
    DateTimeField,
    IntField,
    BooleanField,
    ListField,
    signals,
)

CATEGORY_CHOICES = (
    "Construction",
    "IT & Software",
    "Healthcare & Medical",
    "Electrical & Power",
    "Transportation",
    "Consultancy Services",
    "Defence & Security",
    "Agriculture",
    "Education",
    "Water & Sanitation",
    "Telecommunications",
    "Other",
)

INDIAN_STATES = (
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal", "Delhi (NCT)", "Jammu and Kashmir", "Ladakh",
    "Chandigarh", "Puducherry", "PAN India",
)

STATUS_OPEN = "open"
STATUS_EXPIRING = "expiring_soon"
STATUS_CLOSED = "closed"
STATUS_AWARDED = "awarded"

STATUS_CHOICES = (STATUS_OPEN, STATUS_EXPIRING, STATUS_CLOSED, STATUS_AWARDED)


class Tender(Document):
    """A single government tender / buying opportunity."""

    reference_no = StringField(max_length=120, required=True, unique=True)
    title = StringField(max_length=500, required=True)
    department = StringField(max_length=300, required=True)
    category = StringField(max_length=100, choices=CATEGORY_CHOICES, default="Other")
    state = StringField(max_length=100, choices=INDIAN_STATES, default="PAN India")
    location = StringField(max_length=200, default="")
    description = StringField(default="")

    estimated_value = FloatField(default=0.0)  # in INR
    emd_amount = FloatField(default=0.0)  # earnest money deposit, in INR

    publish_date = DateTimeField(default=datetime.datetime.utcnow)
    deadline = DateTimeField(required=True)  # bid submission deadline
    opening_date = DateTimeField(null=True)

    source_portal = StringField(max_length=200, default="")
    source_url = StringField(max_length=500, default="")

    status = StringField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    tags = ListField(StringField(max_length=50), default=list)

    created_at = DateTimeField(default=datetime.datetime.utcnow)
    updated_at = DateTimeField(default=datetime.datetime.utcnow)

    meta = {
        "collection": "tenders",
        "indexes": [
            "reference_no",
            "category",
            "state",
            "deadline",
            "status",
            {"fields": ["$title", "$department", "$description"]},
        ],
        "ordering": ["-publish_date"],
    }

    def __str__(self):
        return f"{self.reference_no} — {self.title[:60]}"

    def days_remaining(self):
        delta = self.deadline - datetime.datetime.utcnow()
        return delta.days

    def refresh_status(self, save=True):
        """Recompute status from the deadline. Called by the scraper/alert engine."""
        days_left = self.days_remaining()
        if days_left < 0:
            self.status = STATUS_CLOSED
        elif days_left <= 3:
            self.status = STATUS_EXPIRING
        else:
            self.status = STATUS_OPEN
        if save:
            self.save()
        return self.status

    @classmethod
    def pre_save(cls, sender, document, **kwargs):
        document.updated_at = datetime.datetime.utcnow()


try:
    signals.pre_save.connect(Tender.pre_save, sender=Tender)
except RuntimeError:
    # "blinker" isn't installed — see requirements.txt. Tenders will still
    # save/query fine; only the automatic `updated_at` bump on save is lost,
    # so we fall back to setting it manually wherever we mutate a Tender.
    pass


class TenderWatch(Document):
    """A saved search / watchlist entry owned by a Django auth user."""

    user_id = IntField(required=True)
    keyword = StringField(max_length=200, default="")
    category = StringField(max_length=100, default="")
    state = StringField(max_length=100, default="")
    min_value = FloatField(default=0.0)
    max_value = FloatField(default=0.0)
    created_at = DateTimeField(default=datetime.datetime.utcnow)

    meta = {"collection": "tender_watches", "ordering": ["-created_at"]}

    def __str__(self):
        return f"Watch(user={self.user_id}, keyword={self.keyword!r})"


class AlertPreference(Document):
    """Per-user alert configuration used by the AlertEngine."""

    user_id = IntField(required=True, unique=True)
    email = StringField(max_length=255, default="")
    enabled = BooleanField(default=True)
    remind_days_before = ListField(IntField(), default=lambda: [7, 3, 1])
    categories = ListField(StringField(max_length=100), default=list)  # empty = all
    states = ListField(StringField(max_length=100), default=list)  # empty = all
    last_notified = DateTimeField(null=True)

    meta = {"collection": "alert_preferences"}

    def __str__(self):
        return f"AlertPreference(user={self.user_id})"

    @classmethod
    def get_or_create_for_user(cls, user_id, email=""):
        """
        Safe stand-in for MongoEngine's get_or_create(), which has been
        unreliable about stripping the `defaults` kwarg across versions
        (raises FieldDoesNotExist on some installs). Does a plain
        find-else-create instead.
        """
        pref = cls.objects.filter(user_id=user_id).first()
        if pref:
            return pref, False
        pref = cls(user_id=user_id, email=email)
        pref.save()
        return pref, True


class AlertLog(Document):
    """Record of alerts already sent, to avoid duplicate notifications."""

    user_id = IntField(required=True)
    tender_reference_no = StringField(required=True)
    sent_at = DateTimeField(default=datetime.datetime.utcnow)
    channel = StringField(max_length=30, default="email")

    meta = {
        "collection": "alert_logs",
        "indexes": [{"fields": ["user_id", "tender_reference_no"], "unique": True}],
    }