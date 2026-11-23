"""Limites de autenticação compartilhados entre processos pelo PostgreSQL."""
import logging
import math
from datetime import timedelta
from functools import wraps
from ipaddress import ip_address, ip_network

from django.conf import settings
from django.db import DatabaseError, transaction
from django.shortcuts import render
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import AuthAttemptWindow

logger = logging.getLogger(__name__)
WINDOW = timedelta(minutes=15)


def client_address(request):
    peer = request.META.get("REMOTE_ADDR", "")
    networks = [ip_network(value) for value in getattr(settings, "AUTH_TRUSTED_PROXY_NETWORKS", [])]
    chain = [part.strip() for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if part.strip()]
    chain.append(peer)
    try:
        for value in reversed(chain):
            address = ip_address(value)
            if not any(address in network for network in networks):
                return str(address)
        return str(ip_address(chain[0]))
    except ValueError:
        return peer or "unknown"


def consume_attempt(scope, account, address):
    now = timezone.now()
    identities = [("origin", address, 60)]
    if account:
        identities.append(("account", account.strip().casefold(), 10))
    keys = [(salted_hmac("pm-auth-limit", f"{scope}:{kind}:{value}").hexdigest(), limit)
            for kind, value, limit in identities]
    with transaction.atomic():
        expired = list(AuthAttemptWindow.objects.filter(expires_at__lte=now)
                       .order_by("expires_at").values_list("pk", flat=True)[:100])
        AuthAttemptWindow.objects.filter(pk__in=expired, expires_at__lte=now).delete()
        windows = []
        for key, limit in keys:
            row, _ = AuthAttemptWindow.objects.get_or_create(key=key, defaults={"expires_at": now + WINDOW})
            row = AuthAttemptWindow.objects.select_for_update().get(pk=row.pk)
            if row.expires_at <= now:
                row.attempts, row.expires_at = 0, now + WINDOW
            if row.attempts >= limit:
                return math.ceil((row.expires_at - now).total_seconds())
            windows.append((row, limit))
        for row, _ in windows:
            row.attempts += 1
            row.save(update_fields=["attempts", "expires_at"])
    return 0


def limit_authentication(scope):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method != "POST" or (scope == "invitation" and request.POST.get("action") != "register"):
                return view(request, *args, **kwargs)
            try:
                retry = consume_attempt("register" if scope == "invitation" else scope,
                                        request.POST.get("username", ""), client_address(request))
            except DatabaseError:
                logger.error("Proteção de autenticação indisponível")
                response = render(request, "auth/limited.html", {"unavailable": True}, status=503)
                response["Retry-After"] = "60"
            else:
                if not retry:
                    return view(request, *args, **kwargs)
                logger.warning("Limite de autenticação atingido; fluxo=%s", scope)
                response = render(request, "auth/limited.html", {"minutes": max(1, math.ceil(retry / 60))}, status=429)
                response["Retry-After"] = str(retry)
            response["Cache-Control"] = "no-store"
            return response
        return wrapped
    return decorator
