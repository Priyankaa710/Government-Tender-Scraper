"""
TenderParser — turns raw scraped dicts into normalized tender records,
using regex to extract/validate reference numbers and `datetime` to
normalize deadlines.
"""

import re
import logging
import datetime
from typing import Optional

logger = logging.getLogger("scraper")

# Matches things like "ABC/2025/1234", "GEM/2025/B/123456", "CPPP-2025-00123",
# "Tender No: MH/PWD/2025/00981" etc. Captures the "clean" reference token.
REFERENCE_NO_PATTERN = re.compile(
    r"""(?:Tender\s*No\.?\s*[:\-]?\s*)?      # optional "Tender No:" prefix
        (
            [A-Z0-9]{2,15}                    # leading alpha-numeric block
            (?:[\/\-][A-Z0-9]{1,15}){1,6}     # 1-6 more blocks separated by / or -
        )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# A stricter validator: reference must contain at least one 4-digit year
# and at least one separator, to reject accidental matches like plain words.
REFERENCE_NO_VALIDATOR = re.compile(r"^[A-Z0-9]+([\/\-][A-Z0-9]+)+$", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"(19|20)\d{2}")

DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%Y-%m-%d %H:%M:%S",
)


class TenderParser:
    """Stateless helper class that normalizes one raw tender payload at a time."""

    @staticmethod
    def extract_reference_no(text: str) -> Optional[str]:
        """Extract and validate a tender reference number from free text using regex."""
        if not text:
            return None
        match = REFERENCE_NO_PATTERN.search(text)
        if not match:
            return None
        candidate = match.group(1).upper()
        if not REFERENCE_NO_VALIDATOR.match(candidate):
            return None
        if not YEAR_PATTERN.search(candidate):
            # Still allow it through, but log for visibility — some portals
            # use non-year reference schemes (e.g. purely sequential IDs).
            logger.debug("Reference %s has no embedded year — accepting anyway", candidate)
        return candidate

    @staticmethod
    def parse_date(value) -> Optional[datetime.datetime]:
        """Best-effort parse of a date string coming from a scraped portal payload."""
        if value is None:
            return None
        if isinstance(value, datetime.datetime):
            return value
        if isinstance(value, datetime.date):
            return datetime.datetime.combine(value, datetime.time.min)
        value = str(value).strip()
        for fmt in DATE_FORMATS:
            try:
                return datetime.datetime.strptime(value, fmt)
            except ValueError:
                continue
        logger.warning("Could not parse date value: %r", value)
        return None

    @classmethod
    def normalize(cls, raw: dict) -> Optional[dict]:
        """
        Convert one raw scraped record into a clean dict ready for Tender().save().
        Returns None (and logs) if the record is missing required fields.
        """
        title = (raw.get("title") or "").strip()
        department = (raw.get("department") or "Unknown Department").strip()
        deadline = cls.parse_date(raw.get("deadline"))

        if not title or not deadline:
            logger.warning("Skipping record — missing title or unparsable deadline: %r", raw)
            return None

        reference_no = raw.get("reference_no") or cls.extract_reference_no(
            raw.get("reference_text", "") or title
        )
        if not reference_no:
            # Fall back to a deterministic synthetic reference so we never drop a tender.
            reference_no = f"AUTO/{deadline.year}/{abs(hash(title)) % 100000:05d}"

        return {
            "reference_no": reference_no,
            "title": title,
            "department": department,
            "category": raw.get("category") or "Other",
            "state": raw.get("state") or "PAN India",
            "location": raw.get("location", ""),
            "description": raw.get("description", ""),
            "estimated_value": float(raw.get("estimated_value") or 0),
            "emd_amount": float(raw.get("emd_amount") or 0),
            "publish_date": cls.parse_date(raw.get("publish_date")) or datetime.datetime.utcnow(),
            "deadline": deadline,
            "opening_date": cls.parse_date(raw.get("opening_date")),
            "source_portal": raw.get("source_portal", ""),
            "source_url": raw.get("source_url", ""),
            "tags": raw.get("tags", []),
        }


# --- Filtering helpers (list comprehensions + tuples, as required) ----------

def filter_by_category(tenders, category: str):
    """tenders: iterable of dicts or Tender objects with a .category/['category']."""
    def get_cat(t):
        return t.category if hasattr(t, "category") else t.get("category")
    return [t for t in tenders if get_cat(t) == category]


def filter_by_state(tenders, state: str):
    def get_state(t):
        return t.state if hasattr(t, "state") else t.get("state")
    return [t for t in tenders if get_state(t) == state]


def filter_upcoming(tenders, within_days: int = 30, now: Optional[datetime.datetime] = None):
    """Return tenders whose deadline falls within the next `within_days` days."""
    now = now or datetime.datetime.utcnow()

    def get_deadline(t):
        return t.deadline if hasattr(t, "deadline") else t.get("deadline")

    # tuple pairs of (tender, days_remaining), then filtered down via comprehension
    paired = tuple((t, (get_deadline(t) - now).days) for t in tenders)
    return [t for t, days in paired if 0 <= days <= within_days]


def filter_expiring_soon(tenders, threshold_days: int = 3, now: Optional[datetime.datetime] = None):
    return filter_upcoming(tenders, within_days=threshold_days, now=now)
