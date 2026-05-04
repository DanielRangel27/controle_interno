"""URL configuration for controle_interno project."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", RedirectView.as_view(pattern_name="core:dashboard", permanent=False)),
    path("painel/", include(("core.urls", "core"), namespace="core")),
    path("fazendaria/", include(("fazendaria.urls", "fazendaria"), namespace="fazendaria")),
    path("geral/", include(("geral.urls", "geral"), namespace="geral")),
]
