"""Middleware that exposes the current request actor to audit signals.

Django signals do not have access to the ``request``, so we stash the relevant
bits of information in a thread-local object during the request/response cycle.
The audit signal handlers read from there to record who performed the change.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse

_state = threading.local()


def get_current_actor() -> Any | None:
    """Return the user that initiated the current request, if any."""

    return getattr(_state, "actor", None)


def get_current_ip() -> str | None:
    """Return the IP address associated with the current request, if any."""

    return getattr(_state, "ip", None)


def _client_ip(request: HttpRequest) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


class CurrentRequestMiddleware:
    """Save the current request's actor/ip so audit signals can use them."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        actor = user if (user is not None and user.is_authenticated) else None
        _state.actor = actor
        _state.ip = _client_ip(request)
        try:
            return self.get_response(request)
        finally:
            _state.actor = None
            _state.ip = None
