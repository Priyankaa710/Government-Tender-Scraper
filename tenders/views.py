import csv
import datetime

from bson.errors import InvalidId
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from mongoengine.errors import DoesNotExist, ValidationError

from .analytics import build_dashboard_stats
from .forms import TenderFilterForm, TenderWatchForm, AlertPreferenceForm, TenderCreateForm
from .models import Tender, TenderWatch, AlertPreference


def _get_tender_or_404(pk):
    try:
        return Tender.objects.get(id=pk)
    except (DoesNotExist, ValidationError, InvalidId):
        raise Http404("Tender not found")


def dashboard(request):
    stats = build_dashboard_stats()
    upcoming_deadlines = (
        Tender.objects.filter(status__ne="closed").order_by("deadline")[:8]
    )
    recent_tenders = Tender.objects.order_by("-publish_date")[:6]
    return render(
        request,
        "tenders/dashboard.html",
        {
            "stats": stats,
            "upcoming_deadlines": upcoming_deadlines,
            "recent_tenders": recent_tenders,
        },
    )


def tender_list(request):
    form = TenderFilterForm(request.GET or None)
    qs = Tender.objects.all()

    if form.is_valid():
        data = form.cleaned_data
        if data.get("q"):
            q = data["q"]
            qs = qs.filter(
                __raw__={
                    "$or": [
                        {"title": {"$regex": q, "$options": "i"}},
                        {"department": {"$regex": q, "$options": "i"}},
                        {"reference_no": {"$regex": q, "$options": "i"}},
                    ]
                }
            )
        if data.get("category"):
            qs = qs.filter(category=data["category"])
        if data.get("state"):
            qs = qs.filter(state=data["state"])
        if data.get("status"):
            qs = qs.filter(status=data["status"])
        if data.get("min_value"):
            qs = qs.filter(estimated_value__gte=data["min_value"])
        if data.get("max_value"):
            qs = qs.filter(estimated_value__lte=data["max_value"])
        if data.get("deadline_within_days") is not None and data.get("deadline_within_days") != "":
            cutoff = datetime.datetime.utcnow() + datetime.timedelta(days=data["deadline_within_days"])
            qs = qs.filter(deadline__lte=cutoff)
        sort = data.get("sort") or "deadline"
        qs = qs.order_by(sort)
    else:
        qs = qs.order_by("deadline")

    paginator = Paginator(list(qs), 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "tenders/tender_list.html",
        {"form": form, "page_obj": page_obj, "total_count": paginator.count},
    )


def tender_detail(request, pk):
    tender = _get_tender_or_404(pk)
    is_watched = False
    if request.user.is_authenticated:
        is_watched = TenderWatch.objects.filter(
            user_id=request.user.id, keyword=tender.reference_no
        ).first() is not None
    return render(request, "tenders/tender_detail.html", {"tender": tender, "is_watched": is_watched})


def export_csv(request):
    """Export the currently filtered tender list to CSV."""
    form = TenderFilterForm(request.GET or None)
    qs = Tender.objects.all()
    if form.is_valid():
        data = form.cleaned_data
        if data.get("category"):
            qs = qs.filter(category=data["category"])
        if data.get("state"):
            qs = qs.filter(state=data["state"])
        if data.get("status"):
            qs = qs.filter(status=data["status"])
        if data.get("q"):
            qs = qs.filter(title__icontains=data["q"])

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="tender_trail_export.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Reference No", "Title", "Department", "Category", "State", "Location",
        "Estimated Value (INR)", "Deadline", "Status", "Source Portal", "Source URL",
    ])
    for t in qs.order_by("deadline"):
        writer.writerow([
            t.reference_no, t.title, t.department, t.category, t.state, t.location,
            t.estimated_value, t.deadline.strftime("%Y-%m-%d %H:%M"), t.status,
            t.source_portal, t.source_url,
        ])
    return response


@login_required
def watchlist(request):
    if request.method == "POST":
        form = TenderWatchForm(request.POST)
        if form.is_valid():
            data = {k: v for k, v in form.cleaned_data.items() if v not in ("", None)}
            TenderWatch(user_id=request.user.id, **data).save()
            messages.success(request, "Saved search added to your watchlist.")
            return redirect("tenders:watchlist")
    else:
        form = TenderWatchForm()

    watches = TenderWatch.objects.filter(user_id=request.user.id).order_by("-created_at")
    return render(request, "tenders/watchlist.html", {"form": form, "watches": watches})


@login_required
def watchlist_delete(request, pk):
    watch = get_object_or_404(TenderWatch, id=pk, user_id=request.user.id)
    watch.delete()
    messages.success(request, "Removed from your watchlist.")
    return redirect("tenders:watchlist")


@login_required
def alert_preferences(request):
    pref, _ = AlertPreference.get_or_create_for_user(request.user.id, email=request.user.email)
    if request.method == "POST":
        form = AlertPreferenceForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            pref.email = data["email"] or request.user.email
            pref.enabled = data["enabled"]
            days = [int(d.strip()) for d in data["remind_days_before"].split(",") if d.strip().isdigit()]
            pref.remind_days_before = days or [7, 3, 1]
            pref.categories = data["categories"]
            pref.states = data["states"]
            pref.save()
            messages.success(request, "Alert preferences updated.")
            return redirect("tenders:alert_preferences")
    else:
        form = AlertPreferenceForm(
            initial={
                "email": pref.email,
                "enabled": pref.enabled,
                "remind_days_before": ",".join(str(d) for d in pref.remind_days_before),
                "categories": pref.categories,
                "states": pref.states,
            }
        )
    return render(request, "tenders/alert_preferences.html", {"form": form, "pref": pref})


@login_required
def tender_create(request):
    """Let a signed-in user add a tender manually through the app UI."""
    if request.method == "POST":
        form = TenderCreateForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            tender = Tender(
                reference_no=data["reference_no"],
                title=data["title"],
                department=data["department"],
                category=data["category"],
                state=data["state"],
                location=data.get("location", ""),
                description=data.get("description", ""),
                estimated_value=data.get("estimated_value") or 0,
                emd_amount=data.get("emd_amount") or 0,
                deadline=data["deadline"],
                opening_date=data.get("opening_date"),
                source_portal=data.get("source_portal") or "Manual Entry",
                source_url=data.get("source_url", ""),
            )
            tender.save()
            tender.refresh_status()
            messages.success(request, f"Tender {tender.reference_no} added.")
            return redirect("tenders:tender_detail", pk=str(tender.id))
    else:
        form = TenderCreateForm()

    return render(request, "tenders/tender_form.html", {"form": form})