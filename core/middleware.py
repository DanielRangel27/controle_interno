"""Custom middleware exposing automatic backup feedback to the user."""

from __future__ import annotations

from collections.abc import Callable

from django.contrib import messages
from django.http import HttpRequest, HttpResponse

from .process_backup_signals import (
    get_last_backup_status,
    reset_status,
)


class BackupStatusFlashMiddleware:
    """Surface the result of automatic backups as Django flash messages.

    The signal handler (``core.process_backup_signals``) records the outcome
    of the latest backup attempt in a thread-local. After the request is
    handled we read it and add a user-facing message accordingly. The
    thread-local is always reset, so leftover state never leaks between
    requests.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        reset_status()
        try:
            response = self.get_response(request)
            self._flash(request)
            return response
        finally:
            reset_status()

    @staticmethod
    def _flash(request: HttpRequest) -> None:
        status = get_last_backup_status()
        if status is None:
            return

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return

        if status.outcome == "offline":
            pending = status.pending_commits
            if pending:
                text = (
                    "Backup automático: sem conexão. Sua alteração foi salva "
                    f"localmente ({pending} commit(s) pendente(s)) e será "
                    "enviada quando a internet voltar."
                )
            else:
                text = (
                    "Backup automático: sem conexão. Sua alteração foi salva "
                    "localmente e será enviada quando a internet voltar."
                )
            messages.warning(request, text)
        elif status.outcome == "error":
            messages.error(
                request,
                "Backup automático falhou. Verifique os logs do servidor "
                "ou rode `python manage.py backup_git` manualmente.",
            )
