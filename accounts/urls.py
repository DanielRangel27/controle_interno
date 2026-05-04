"""URL routes for the accounts module."""

from __future__ import annotations

from django.urls import path

from .views import SignupPendingView, SignupView

app_name = "accounts"

urlpatterns = [
    path("cadastro/", SignupView.as_view(), name="signup"),
    path("cadastro/pendente/", SignupPendingView.as_view(), name="signup_pendente"),
]
