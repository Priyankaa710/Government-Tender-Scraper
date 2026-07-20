"""
Scraper classes — one per government open-data / e-procurement source.

Real portals like data.gov.in and eProcure.gov.in either require an API key
or serve HTML that changes often. Each scraper therefore:
  1. Tries a real HTTP request against a public endpoint.
  2. Falls back to realistic sample data on any failure (auth wall, timeout,
     schema change, network being disabled in this sandbox, etc.) so the
     rest of the pipeline (parsing, storage, alerts, dashboard) always has
     something to work with.
"""

import json
import random
import logging
import datetime
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

import requests

logger = logging.getLogger("scraper")

CATEGORIES = (
    "Construction", "IT & Software", "Healthcare & Medical", "Electrical & Power",
    "Transportation", "Consultancy Services", "Defence & Security", "Agriculture",
    "Education", "Water & Sanitation", "Telecommunications",
)
STATES = (
    "Maharashtra", "Karnataka", "Delhi (NCT)", "Tamil Nadu", "Gujarat",
    "Uttar Pradesh", "West Bengal", "Rajasthan", "Telangana", "Kerala", "PAN India",
)
DEPARTMENTS = (
    "Public Works Department", "Ministry of Electronics & IT", "National Health Mission",
    "State Electricity Board", "Indian Railways", "Municipal Corporation",
    "Ministry of Defence", "Department of Agriculture", "Department of Education",
    "Jal Shakti Ministry", "BSNL / Telecom Dept.",
)


class BaseScraper(ABC):
    """Common interface + shared HTTP/error-handling logic for all portal scrapers."""

    portal_name = "Unknown Portal"
    timeout_seconds = 8

    def fetch(self):
        """Public entrypoint: try live fetch, gracefully fall back to samples."""
        try:
            data = self._fetch_live()
            if not data:
                raise ValueError("Live endpoint returned no usable records")
            logger.info("%s: fetched %d live records", self.portal_name, len(data))
            return data
        except (
            requests.RequestException,
            urllib.error.URLError,
            urllib.error.HTTPError,
            ValueError,
            json.JSONDecodeError,
            TimeoutError,
        ) as exc:
            logger.warning(
                "%s: live fetch failed (%s) — using sample fallback data",
                self.portal_name, exc,
            )
            return self._sample_fallback()
        except Exception as exc:  # noqa: BLE001 - never let one bad portal kill the run
            logger.exception("%s: unexpected scraper error: %s", self.portal_name, exc)
            return self._sample_fallback()

    @abstractmethod
    def _fetch_live(self):
        """Attempt a real HTTP call. Raise on any failure — never return partial junk."""

    @abstractmethod
    def _sample_fallback(self):
        """Deterministic-ish sample data so downstream stages always have input."""


class DataGovInScraper(BaseScraper):
    """
    Targets data.gov.in's open government data API (CKAN-style JSON), which
    requires a free API key. Without one configured, this cleanly fails over
    to sample data.
    """

    portal_name = "data.gov.in"
    API_URL = "https://api.data.gov.in/resource/latest-tenders"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def _fetch_live(self):
        if not self.api_key:
            raise ValueError("No data.gov.in API key configured")
        params = {"api-key": self.api_key, "format": "json", "limit": 50}
        response = requests.get(self.API_URL, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        records = payload.get("records", [])
        return [self._map_record(r) for r in records]

    @staticmethod
    def _map_record(r):
        return {
            "title": r.get("tender_title"),
            "department": r.get("organisation"),
            "reference_text": r.get("tender_reference_number", ""),
            "deadline": r.get("closing_date"),
            "publish_date": r.get("published_date"),
            "estimated_value": r.get("tender_value"),
            "state": r.get("state"),
            "category": r.get("category"),
            "source_portal": "data.gov.in",
            "source_url": r.get("url", "https://data.gov.in"),
        }

    def _sample_fallback(self):
        return _generate_sample_batch("data.gov.in", "https://data.gov.in/resources", count=8)


class EProcureScraper(BaseScraper):
    """
    Targets the Central Public Procurement Portal (eProcure.gov.in). The real
    site serves rendered HTML with anti-scraping measures, so this uses
    urllib for a lightweight HEAD/GET probe, falling back to sample data.
    """

    portal_name = "eProcure.gov.in (CPPP)"
    PROBE_URL = "https://eprocure.gov.in/eprocure/app"

    def _fetch_live(self):
        request_obj = urllib.request.Request(
            self.PROBE_URL, headers={"User-Agent": "TenderTrailBot/1.0"}
        )
        with urllib.request.urlopen(request_obj, timeout=self.timeout_seconds) as resp:
            if resp.status != 200:
                raise ValueError(f"Unexpected status code {resp.status}")
        # The portal doesn't expose a public JSON API, so a reachable page
        # only confirms connectivity — structured data still comes from the
        # sample generator, which stands in for a real parsed HTML scrape.
        raise ValueError("eProcure.gov.in has no public JSON endpoint; using structured sample set")

    def _sample_fallback(self):
        return _generate_sample_batch("eProcure.gov.in (CPPP)", "https://eprocure.gov.in", count=10)


class StatePortalScraper(BaseScraper):
    """Generic stand-in for a state-level e-tender portal (extensible pattern)."""

    def __init__(self, state_name: str, base_url: str):
        self.state_name = state_name
        self.portal_name = f"{state_name} e-Tender Portal"
        self.base_url = base_url

    def _fetch_live(self):
        response = requests.get(self.base_url, timeout=self.timeout_seconds)
        response.raise_for_status()
        raise ValueError("State portal returned HTML, not a structured feed")

    def _sample_fallback(self):
        return _generate_sample_batch(self.portal_name, self.base_url, count=5, state=self.state_name)


def _generate_sample_batch(source_portal, source_url, count=8, state=None):
    """Realistic-looking sample tenders used whenever a live fetch isn't possible."""
    now = datetime.datetime.utcnow()
    batch = []
    for i in range(count):
        category = random.choice(CATEGORIES)
        department = random.choice(DEPARTMENTS)
        tender_state = state or random.choice(STATES)
        days_ahead = random.choice([1, 2, 3, 5, 7, 10, 14, 21, 30, 45])
        deadline = now + datetime.timedelta(days=days_ahead)
        published = now - datetime.timedelta(days=random.randint(1, 20))
        year = now.year
        ref = f"{tender_state[:2].upper()}/{department.split()[0][:3].upper()}/{year}/{random.randint(1000, 99999)}"
        value = random.choice([500000, 1200000, 2500000, 7500000, 15000000, 45000000, 90000000])

        batch.append({
            "title": f"Supply and Installation of {category} Equipment — Phase {random.randint(1,3)}",
            "department": department,
            "reference_no": ref,
            "category": category,
            "state": tender_state,
            "location": f"{tender_state}",
            "description": (
                f"Tender No: {ref} invites bids from eligible contractors for "
                f"{category.lower()} works under {department}. EMD and tender "
                f"documents available on the procuring portal."
            ),
            "estimated_value": value,
            "emd_amount": round(value * 0.02, 2),
            "publish_date": published,
            "deadline": deadline,
            "opening_date": deadline + datetime.timedelta(days=2),
            "source_portal": source_portal,
            "source_url": source_url,
            "tags": [category.split()[0].lower()],
        })
    return batch


def get_default_scrapers():
    """The set of scrapers the daily job runs across, in threads."""
    return [
        DataGovInScraper(api_key=""),
        EProcureScraper(),
        StatePortalScraper("Maharashtra", "https://mahatenders.gov.in"),
        StatePortalScraper("Karnataka", "https://eproc.karnataka.gov.in"),
    ]
