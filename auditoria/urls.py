"""URL routes for the auditoria module."""

from __future__ import annotations

from django.urls import path

from .views import AuditLogListView

urlpatterns = [
    path("", AuditLogListView.as_view(), name="lista"),
]
