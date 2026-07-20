from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import api_views

app_name = "tenders_api"

urlpatterns = [
    path("tenders/", api_views.TenderListCreateAPIView.as_view(), name="tender-list"),
    path("tenders/<str:pk>/", api_views.TenderDetailAPIView.as_view(), name="tender-detail"),
    path("watches/", api_views.TenderWatchListCreateAPIView.as_view(), name="watch-list"),
    path("watches/<str:pk>/", api_views.TenderWatchDetailAPIView.as_view(), name="watch-detail"),
    path("alert-preferences/", api_views.AlertPreferenceAPIView.as_view(), name="alert-prefs"),
    path("stats/", api_views.TenderStatsAPIView.as_view(), name="stats"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
