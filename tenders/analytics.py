"""
Aggregation helpers that power the dashboard cards and Chart.js graphs.

Uses list comprehensions and tuples (as requested) to slice/summarize the
in-memory tender snapshot pulled from MongoDB.
"""

import datetime

from .models import Tender, CATEGORY_CHOICES, STATUS_EXPIRING, STATUS_OPEN, STATUS_CLOSED


def build_dashboard_stats():
    now = datetime.datetime.utcnow()
    all_tenders = list(Tender.objects.all())

    # tuple of (tender, days_remaining) pairs — used for deadline-based slicing
    with_days = [(t, (t.deadline - now).days) for t in all_tenders]

    upcoming = [t for t, days in with_days if 0 <= days <= 30 and t.status != STATUS_CLOSED]
    expiring_soon = [t for t, days in with_days if 0 <= days <= 3]
    open_tenders = [t for t in all_tenders if t.status == STATUS_OPEN]
    closed_tenders = [t for t in all_tenders if t.status == STATUS_CLOSED]

    total_value = sum(t.estimated_value or 0 for t in all_tenders)
    open_value = sum(t.estimated_value or 0 for t in open_tenders)

    category_breakdown = [
        {"category": cat, "count": len([t for t in all_tenders if t.category == cat])}
        for cat in CATEGORY_CHOICES
    ]
    category_breakdown = [c for c in category_breakdown if c["count"] > 0]

    state_breakdown = {}
    for t in all_tenders:
        state_breakdown[t.state] = state_breakdown.get(t.state, 0) + 1
    top_states = sorted(state_breakdown.items(), key=lambda kv: kv[1], reverse=True)[:8]

    # Deadlines over the next 14 days, bucketed by date, for a mini calendar/bar chart.
    calendar_buckets = []
    for offset in range(14):
        day = (now + datetime.timedelta(days=offset)).date()
        count = len([t for t in all_tenders if t.deadline.date() == day])
        calendar_buckets.append({"date": day.isoformat(), "count": count})

    return {
        "total_tenders": len(all_tenders),
        "open_tenders": len(open_tenders),
        "closed_tenders": len(closed_tenders),
        "expiring_soon_count": len(expiring_soon),
        "upcoming_30_days": len(upcoming),
        "total_estimated_value": total_value,
        "open_estimated_value": open_value,
        "category_breakdown": category_breakdown,
        "top_states": [{"state": s, "count": c} for s, c in top_states],
        "deadline_calendar": calendar_buckets,
    }
