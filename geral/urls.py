"""URL routes for the geral module."""

from __future__ import annotations

from django.urls import path

from .views import (
    ProcessoCreateView,
    ProcessoDetailView,
    ProcessoExportView,
    ProcessoListView,
    ProcessoUpdateView,
)

urlpatterns = [
    path("", ProcessoListView.as_view(), name="lista"),
    path("novo/", ProcessoCreateView.as_view(), name="criar"),
    path("<int:pk>/", ProcessoDetailView.as_view(), name="detalhe"),
    path("<int:pk>/editar/", ProcessoUpdateView.as_view(), name="editar"),
    path("exportar/<str:formato>/", ProcessoExportView.as_view(), name="exportar"),
]
