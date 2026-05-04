"""Class-based views for the accounts module."""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from .forms import SignupForm

logger = logging.getLogger(__name__)


class SignupView(CreateView):
    """Public signup view; new users are created inactive (await approval)."""

    template_name = "accounts/signup.html"
    form_class = SignupForm
    success_url = reverse_lazy("accounts:signup_pendente")

    def form_valid(self, form: SignupForm):
        user = form.save(commit=False)
        user.is_active = False
        user.save()
        logger.info(
            "user signup awaiting approval",
            extra={"user_id": user.pk, "username": user.get_username()},
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Criar conta"
        return ctx


class SignupPendingView(TemplateView):
    """Confirmation page shown after signup, explaining approval flow."""

    template_name = "accounts/signup_pending.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Cadastro recebido"
        return ctx


def get_pending_users_queryset():
    """Return users that signed up and still wait for activation."""

    return get_user_model().objects.filter(is_active=False).order_by("-date_joined")
