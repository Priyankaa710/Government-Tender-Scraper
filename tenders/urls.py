from django.urls import path

from . import views

app_name = "tenders"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("tenders/", views.tender_list, name="tender_list"),
    path("tenders/add/", views.tender_create, name="tender_create"),
    path("tenders/export/csv/", views.export_csv, name="export_csv"),
    path("tenders/<str:pk>/", views.tender_detail, name="tender_detail"),
    path("watchlist/", views.watchlist, name="watchlist"),
    path("watchlist/<str:pk>/delete/", views.watchlist_delete, name="watchlist_delete"),
    path("preferences/", views.alert_preferences, name="alert_preferences"),
]
