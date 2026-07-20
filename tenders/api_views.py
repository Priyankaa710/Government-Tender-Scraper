"""
DRF API views for business users.

Endpoints operate directly on MongoEngine querysets. Pagination/filtering
is implemented by hand (rather than via DjangoFilterBackend, which expects
Django ORM querysets) to keep things simple and dependency-light.
"""

from bson.errors import InvalidId
from mongoengine.errors import DoesNotExist, NotUniqueError, ValidationError
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Tender, TenderWatch, AlertPreference
from .serializers import TenderSerializer, TenderWatchSerializer, AlertPreferenceSerializer


def _paginate(request, queryset):
    try:
        page = max(int(request.query_params.get("page", 1)), 1)
    except ValueError:
        page = 1
    try:
        page_size = min(max(int(request.query_params.get("page_size", 20)), 1), 100)
    except ValueError:
        page_size = 20
    start = (page - 1) * page_size
    total = queryset.count()
    items = queryset.skip(start).limit(page_size)
    return items, {
        "count": total,
        "page": page,
        "page_size": page_size,
        "num_pages": max((total + page_size - 1) // page_size, 1),
    }


class TenderListCreateAPIView(APIView):
    """
    GET /api/tenders/  — list & filter tenders (category, state, min/max value,
                          deadline range, free-text search via ?q=).
    POST /api/tenders/ — create a tender (authenticated, e.g. for manual entry).
    """

    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        qs = Tender.objects.all()

        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        state = request.query_params.get("state")
        if state:
            qs = qs.filter(state=state)

        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        min_value = request.query_params.get("min_value")
        if min_value:
            qs = qs.filter(estimated_value__gte=float(min_value))

        max_value = request.query_params.get("max_value")
        if max_value:
            qs = qs.filter(estimated_value__lte=float(max_value))

        deadline_before = request.query_params.get("deadline_before")
        if deadline_before:
            qs = qs.filter(deadline__lte=deadline_before)

        query = request.query_params.get("q")
        if query:
            qs = qs.filter(title__icontains=query)

        ordering = request.query_params.get("ordering", "deadline")
        qs = qs.order_by(ordering)

        items, meta = _paginate(request, qs)
        serializer = TenderSerializer(items, many=True)
        return Response({**meta, "results": serializer.data})

    def post(self, request):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        serializer = TenderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tender = serializer.save()
        except NotUniqueError:
            return Response(
                {"reference_no": "A tender with this reference number already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(TenderSerializer(tender).data, status=status.HTTP_201_CREATED)


class TenderDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_object(self, pk):
        try:
            return Tender.objects.get(id=pk)
        except (DoesNotExist, ValidationError, InvalidId):
            return None

    def get(self, request, pk):
        tender = self.get_object(pk)
        if not tender:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(TenderSerializer(tender).data)

    def put(self, request, pk):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        tender = self.get_object(pk)
        if not tender:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = TenderSerializer(tender, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        tender = self.get_object(pk)
        if not tender:
            return Response(status=status.HTTP_404_NOT_FOUND)
        tender.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TenderWatchListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        watches = TenderWatch.objects.filter(user_id=request.user.id)
        return Response(TenderWatchSerializer(watches, many=True).data)

    def post(self, request):
        serializer = TenderWatchSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        watch = serializer.save()
        return Response(TenderWatchSerializer(watch).data, status=status.HTTP_201_CREATED)


class TenderWatchDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, request, pk):
        try:
            return TenderWatch.objects.get(id=pk, user_id=request.user.id)
        except (DoesNotExist, ValidationError, InvalidId):
            return None

    def delete(self, request, pk):
        watch = self.get_object(request, pk)
        if not watch:
            return Response(status=status.HTTP_404_NOT_FOUND)
        watch.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AlertPreferenceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        pref, _ = AlertPreference.get_or_create_for_user(request.user.id, email=request.user.email)
        return Response(AlertPreferenceSerializer(pref).data)

    def put(self, request):
        pref, _ = AlertPreference.get_or_create_for_user(request.user.id, email=request.user.email)
        serializer = AlertPreferenceSerializer(pref, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class TenderStatsAPIView(APIView):
    """Aggregate numbers powering the dashboard charts."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from .analytics import build_dashboard_stats

        return Response(build_dashboard_stats())