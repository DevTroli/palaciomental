"""Gera URLs de tenants sem alterar permissões ou resolver organizações."""
import re
from urllib.parse import urlsplit

_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.ASCII)


def build_tenant_url(hostname, *, debug=False, request_host="", request_scheme="https"):
    hostname = (hostname or "").strip().lower().rstrip(".")
    labels = hostname.split(".")
    if len(hostname) > 253 or len(labels) < 2 or not all(_LABEL.fullmatch(label) for label in labels):
        return None
    is_local = hostname.endswith(".localhost")
    if not is_local:
        return f"https://{hostname}/"
    if not debug or request_scheme not in {"http", "https"}:
        return None
    try:
        origin = urlsplit("//" + request_host)
        origin_host = (origin.hostname or "").lower()
        port = origin.port
    except ValueError:
        return None
    if origin.username or origin.password or origin.path or origin.query or origin.fragment:
        return None
    if origin_host not in {"localhost", "127.0.0.1", "::1"} and not origin_host.endswith(".localhost"):
        return None
    suffix = f":{port}" if port is not None else ""
    return f"{request_scheme}://{hostname}{suffix}/"
