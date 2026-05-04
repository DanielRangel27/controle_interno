"""App config for the auditoria module."""

from __future__ import annotations

from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    name = "auditoria"
    verbose_name = "Auditoria"

    def ready(self) -> None:
        from . import signals

        signals.connect_auditable_signals()
