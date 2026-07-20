from .models import Tender, STATUS_EXPIRING


def nav_stats(request):
    """Small counts shown in the navbar/sidebar badges. Fails soft if Mongo is down."""
    try:
        expiring_count = Tender.objects.filter(status=STATUS_EXPIRING).count()
        total_open = Tender.objects.filter(status__ne="closed").count()
    except Exception:
        expiring_count, total_open = 0, 0
    return {"nav_expiring_count": expiring_count, "nav_open_count": total_open}
