"""Envia ao Guardião apenas o identificador e a URL das referências atuais."""

import json
from uuid import UUID
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from plataforma.models import ProjectLink
from plataforma.rls import system_context


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Command(BaseCommand):
    help = "Envia os links existentes ao serviço Guardião em lotes de até 100."

    def handle(self, *args, **options):
        endpoint = getattr(settings, "GUARDIAO_API_URL", "")
        token = getattr(settings, "GUARDIAO_SERVICE_TOKEN", "")
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment or not token
                or parsed.path != "/internal/guardiao/links"):
            raise CommandError("Configure GUARDIAO_API_URL HTTPS e GUARDIAO_SERVICE_TOKEN.")
        opener = build_opener(_NoRedirect())
        root = f"https://{parsed.netloc}/internal/guardiao"

        def post(url, expected, data=b"", snapshot=None):
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if snapshot:
                headers["X-Guardiao-Snapshot"] = snapshot
            request = Request(url, data=data, method="POST", headers=headers)
            try:
                with opener.open(request, timeout=10) as response:  # nosec B310: HTTPS configurado pelo operador
                    if response.status != expected:
                        raise CommandError("O Guardião não aceitou a operação.")
                    return response.read(1025)
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                raise CommandError("Não foi possível comunicar com o Guardião.") from exc

        try:
            response = json.loads(post(f"{root}/snapshot", 201))
            snapshot = str(UUID(response["id"]))
        except (ValueError, TypeError, KeyError) as exc:
            raise CommandError("Resposta inválida ao iniciar sincronização do Guardião.") from exc
        total = 0
        last_id = 0
        while True:
            with system_context():
                rows = list(ProjectLink.objects.filter(pk__gt=last_id).order_by("pk")
                            .values_list("pk", "url")[:100])
            if not rows:
                break
            payload = json.dumps({"links": [{"link_id": pk, "url": url} for pk, url in rows]}).encode()
            post(endpoint, 202, payload, snapshot)
            total += len(rows)
            last_id = rows[-1][0]
        post(f"{root}/snapshot/finish", 204, snapshot=snapshot)
        self.stdout.write(self.style.SUCCESS(f"{total} link(s) enviado(s) ao Guardião."))
