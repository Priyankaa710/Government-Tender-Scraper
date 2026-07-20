from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("login/", views.TenderTrailLoginView.as_view(), name="login"),
    path("logout/", views.TenderTrailLogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
]
