"""URL routes for the core app."""

from __future__ import annotations

from django.urls import path

from .views import (
    BuscaGlobalView,
    DashboardView,
    RelatorioFazendariaView,
    RelatorioGeralView,
    ToggleThemeView,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("buscar/", BuscaGlobalView.as_view(), name="busca"),
    path(
        "relatorios/fazendaria/",
        RelatorioFazendariaView.as_view(),
        name="relatorio_fazendaria",
    ),
    path(
        "relatorios/geral/",
        RelatorioGeralView.as_view(),
        name="relatorio_geral",
    ),
    path("tema/", ToggleThemeView.as_view(), name="toggle_theme"),
]
