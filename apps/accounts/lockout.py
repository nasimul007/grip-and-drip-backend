"""Hooks for django-axes (failed-login lockout)."""
from rest_framework.throttling import BaseThrottle


def login_identifier(request, credentials):
    """The login name: `email` from the API, `username` from the admin form."""
    credentials = credentials or {}
    value = credentials.get("email") or credentials.get("username")
    if not value and request is not None:
        value = request.POST.get("email") or request.POST.get("username")
    return (value or "").strip().lower()


def client_ip(request):
    """Same client IP the API throttles use (honours REST_FRAMEWORK NUM_PROXIES)."""
    return BaseThrottle().get_ident(request)
