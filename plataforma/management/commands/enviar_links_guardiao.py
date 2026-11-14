"""Sincroniza alterações persistentes dos links com o Guardião."""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, transaction

from plataforma.models import GuardiaoLinkPendente, ProjectLink
from plataforma.rls import system_context


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Command(BaseCommand):
    help = "Envia alterações pendentes de links ao Guardião."

    def add_arguments(self, parser):
        parser.add_argument("--continuo", action="store_true", help="Mantém a sincronização ativa em um processo separado.")
        parser.add_argument("--intervalo", type=int, default=30, help="Segundos entre verificações da fila (mínimo: 5).")

    def handle(self, *args, **options):
        if options["intervalo"] < 5:
            raise CommandError("O intervalo deve ser de pelo menos 5 segundos.")
        self._configuracao()
        if not options["continuo"]:
            self._sincronizar()
            return
        while True:
            try:
                close_old_connections()
                self._sincronizar()
            except CommandError as exc:
                self.stderr.write(f"Sincronização do Guardião falhou: {exc}")
            finally:
                close_old_connections()
            time.sleep(options["intervalo"])

    def _configuracao(self):
        endpoint = (getattr(settings, "GUARDIAO_API_URL", "") or "").strip()
        token = (getattr(settings, "GUARDIAO_SERVICE_TOKEN", "") or "").strip()
        if not endpoint:
            raise CommandError("Defina GUARDIAO_API_URL com a URL HTTPS da API do Guardião.")
        if not token:
            raise CommandError("Defina GUARDIAO_SERVICE_TOKEN com o mesmo token configurado na API do Guardião.")
        try:
            parsed = urlsplit(endpoint)
            port = parsed.port
        except ValueError as exc:
            raise CommandError("GUARDIAO_API_URL é inválida; informe a URL HTTPS da API.") from exc
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment or port == 0
                or parsed.path.rstrip("/") not in ("", "/internal/guardiao/links")):
            raise CommandError("GUARDIAO_API_URL deve ser a URL HTTPS da API, sem parâmetros ou credenciais.")
        return f"https://{parsed.netloc}/internal/guardiao/links", token

    def _sincronizar(self):
        endpoint, token = self._configuracao()
        opener = build_opener(_NoRedirect())
        total = 0
        # O lock serializa alterações do mesmo link, inclusive entre workers. A transação
        # só confirma a remoção da fila depois da resposta; uma repetição é idempotente.
        for _ in range(100):
            with transaction.atomic(), system_context():
                pending = GuardiaoLinkPendente.objects.select_for_update().order_by("link_id").first()
                if pending is None:
                    break
                link = ProjectLink.objects.filter(pk=pending.link_id).values("pk", "url").first()
                if link:
                    url, expected = endpoint, 202
                    payload = {"links": [{"link_id": link["pk"], "url": link["url"]}]}
                else:
                    url, expected = endpoint + "/delete", 204
                    payload = {"link_id": pending.link_id}
                request = Request(url, data=json.dumps(payload).encode(), method="POST", headers={
                    "Authorization": f"Bearer {token}", "Content-Type": "application/json",
                })
                try:
                    with opener.open(request, timeout=10) as response:  # nosec B310: HTTPS configurado pelo operador
                        if response.status != expected:
                            raise CommandError("O Guardião não aceitou a operação.")
                except (HTTPError, URLError, TimeoutError, OSError) as exc:
                    raise CommandError("Não foi possível comunicar com o Guardião.") from exc
                pending.delete()
                total += 1
        self.stdout.write(self.style.SUCCESS(f"{total} alteração(ões) sincronizada(s) com o Guardião."))
