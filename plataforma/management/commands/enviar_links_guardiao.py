"""Sincroniza alterações persistentes dos links com o Guardião."""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, transaction
from django.utils import timezone

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
        endpoint, token = self._configuracao()
        if not options["continuo"]:
            self._sincronizar()
            return
        while True:
            try:
                close_old_connections()
                self._sincronizar()
            except CommandError as exc:
                self.stderr.write(f"Sincronização do Guardião falhou: {exc}")
            except Exception:
                self.stderr.write("Sincronização do Guardião falhou; nova tentativa no próximo ciclo.")
            try:
                from plataforma.guardiao_alertas import sincronizar_alertas
                sincronizar_alertas(endpoint, token, build_opener(_NoRedirect()))
            except Exception:
                self.stderr.write("Sincronização de avisos do Guardião falhou; nova tentativa no próximo ciclo.")
            finally:
                close_old_connections()
            time.sleep(options["intervalo"])

    def _configuracao(self):
        override = (getattr(settings, "GUARDIAO_API_URL", "") or "").strip()
        endpoint = override or (getattr(settings, "STATUS_API_URL", "") or "").strip()
        token = (getattr(settings, "GUARDIAO_SERVICE_TOKEN", "") or "").strip()
        if not endpoint:
            raise CommandError("Defina STATUS_API_URL com a URL HTTPS da API de status.")
        if not token:
            raise CommandError("Defina GUARDIAO_SERVICE_TOKEN com o mesmo token configurado na API do Guardião.")
        try:
            parsed = urlsplit(endpoint)
            port = parsed.port
        except ValueError as exc:
            raise CommandError("A URL da API é inválida; informe uma URL HTTPS válida.") from exc
        local_http = (settings.DEBUG and getattr(settings, "GUARDIAO_LOCAL_HTTP", False)
                      and parsed.scheme == "http" and parsed.hostname == "status-api" and port == 8080)
        if ((parsed.scheme != "https" and not local_http) or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment or port == 0
                or parsed.path.rstrip("/") not in (("", "/v1/guardiao/links") if override else ("", "/v1/status"))):
            raise CommandError("A URL da API deve usar HTTPS, sem parâmetros ou credenciais, e apontar para /v1/status ou /v1/guardiao/links.")
        return f"{parsed.scheme}://{parsed.netloc}/v1/guardiao/links", token

    def _sincronizar(self):
        endpoint, token = self._configuracao()
        opener = build_opener(_NoRedirect())
        total = 0
        attempted = set()
        # O lock mantém a ordem das alterações do mesmo link entre workers.
        # Rejeições individuais aguardam correção ou reprocessamento explícito.
        for _ in range(100):
            with transaction.atomic(), system_context():
                pending = (GuardiaoLinkPendente.objects.select_for_update().filter(quarentena=False)
                           .exclude(link_id__in=attempted).order_by("atualizado_em", "link_id").first())
                if pending is None:
                    break
                attempted.add(pending.link_id)
                link = ProjectLink.objects.filter(pk=pending.link_id).values("pk", "url").first()
                if link:
                    url, expected = endpoint, 202
                    method = "POST"
                    payload = {"links": [{"link_id": link["pk"], "url": link["url"]}]}
                else:
                    url, expected = f"{endpoint}/{pending.link_id}", 204
                    method, payload = "DELETE", None
                request = Request(url, data=json.dumps(payload).encode() if payload else None, method=method, headers={
                    "Authorization": f"Bearer {token}", "Content-Type": "application/json",
                })
                try:
                    with opener.open(request, timeout=10) as response:  # nosec B310: HTTPS ou destino fixo de desenvolvimento
                        if response.status != expected:
                            raise CommandError("O Guardião não aceitou a operação.")
                except HTTPError as exc:
                    if method == "POST" and exc.code in {400, 422}:
                        pending.quarentena = True
                        pending.rejeicao_http = exc.code
                        pending.rejeitada_em = timezone.now()
                        pending.save(update_fields=["quarentena", "rejeicao_http", "rejeitada_em", "atualizado_em"])
                        self.stderr.write(f"Link {pending.link_id} em quarentena (HTTP {exc.code}); corrija a URL ou reprocese o ID.")
                        continue
                    raise CommandError("Não foi possível comunicar com o Guardião.") from exc
                except (URLError, TimeoutError, OSError) as exc:
                    raise CommandError("Não foi possível comunicar com o Guardião.") from exc
                pending.delete()
                total += 1
        from plataforma.guardiao_ameacas import verificar_links_salvos
        verificar_links_salvos()
        self.stdout.write(self.style.SUCCESS(f"{total} alteração(ões) sincronizada(s) com o Guardião."))
