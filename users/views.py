from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render, redirect
from django.urls import reverse_lazy

from .forms import RegisterForm


class TenderTrailLoginView(LoginView):
    template_name = "users/login.html"
    redirect_authenticated_user = True


class TenderTrailLogoutView(LogoutView):
    next_page = reverse_lazy("users:login")


def register(request):
    if request.user.is_authenticated:
        return redirect("tenders:dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, "Welcome to Tender Trail! Your account is ready.")
            return redirect("tenders:dashboard")
    else:
        form = RegisterForm()
    return render(request, "users/register.html", {"form": form})
