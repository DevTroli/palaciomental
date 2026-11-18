"""Sondagem HTTP de leitura para o ambiente de homologação."""
import json
import os
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from django.utils.html import escape


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Command(BaseCommand):
    help = "Verifica login, projeto e programa com turma conhecidos em homologação."

    def add_arguments(self, parser):
        parser.add_argument("--origem", required=True)
        parser.add_argument("--publicar-em", help="URL HTTPS de /v1/guardiao/sondagens no Spring.")
        parser.add_argument("--projeto", required=True, type=int)
        parser.add_argument("--titulo-projeto", required=True)
        parser.add_argument("--programa", required=True)
        parser.add_argument("--nome-turma", required=True)

    def handle(self, *args, **options):
        origin = options["origem"].rstrip("/")
        try:
            url = urlsplit(origin)
        except ValueError:
            raise CommandError("Origem HTTPS inválida.") from None
        if (url.scheme != "https" or not url.hostname or url.username is not None
                or url.password is not None or url.path or url.query or url.fragment):
            raise CommandError("Informe a origem HTTPS do tenant de homologação.")
        username = os.environ.get("PM_PROBE_USERNAME")
        password = os.environ.get("PM_PROBE_PASSWORD")
        if not username or not password:
            raise CommandError("Configure PM_PROBE_USERNAME e PM_PROBE_PASSWORD.")

        cookies = CookieJar()
        client = build_opener(NoRedirects(), HTTPCookieProcessor(cookies))
        login = reverse("plataforma:login")
        project = reverse("plataforma:project_detail", args=[options["projeto"]])
        program = reverse("plataforma:institutional_program_detail", args=[options["programa"]])
        try:
            results = self.check_journeys(client, cookies, origin, login, project, program, username, password, options)
        except (URLError, TimeoutError, OSError):
            results = {"login": False, "projetos": False, "programas_e_turmas": False}
        self.stdout.write(json.dumps(results))
        if options.get("publicar_em"):
            self.publish(options["publicar_em"], origin, results)
        if not all(results.values()):
            raise CommandError("Uma ou mais jornadas não responderam como esperado.")

    @staticmethod
    def publish(endpoint, origin, results):
        url = urlsplit(endpoint)
        token = os.environ.get("GUARDIAO_SERVICE_TOKEN")
        if (not token or url.scheme != "https" or not url.hostname or url.username is not None
                or url.path != "/v1/guardiao/sondagens" or url.query or url.fragment):
            raise CommandError("Informe o endpoint HTTPS de sondagens e configure GUARDIAO_SERVICE_TOKEN.")
        request = Request(endpoint, data=json.dumps({"origin": origin, **results}).encode(), headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        })
        try:
            with build_opener(NoRedirects()).open(request, timeout=10) as response:
                if response.status == 204:
                    return
        except (URLError, TimeoutError, OSError):
            pass
        raise CommandError("A API de status não confirmou o recebimento da sondagem.")

    def check_journeys(self, client, cookies, origin, login, project, program, username, password, options):
        with client.open(origin + login, timeout=10) as response:
            page = response.read(512 * 1024)
        token = next((cookie.value for cookie in cookies if cookie.name == "csrftoken"), "")
        results = {"login": False, "projetos": False, "programas_e_turmas": False}
        if not token or b'data-status-probe="organizacao"' not in page:
            return results
        request = Request(origin + login + "?" + urlencode({"next": project}), data=urlencode({
            "username": username, "password": password, "csrfmiddlewaretoken": token,
        }).encode(), headers={"Referer": origin + login})
        try:
            with client.open(request, timeout=10):
                return results
        except HTTPError as response:
            with response:
                if response.code != 302 or response.headers.get("Location") != project:
                    return results
        results["login"] = True
        results["projetos"] = self.contains(client, origin + project, options["titulo_projeto"])
        results["programas_e_turmas"] = self.contains(client, origin + program, options["nome_turma"])
        return results

    @staticmethod
    def contains(client, url, expected):
        if not expected.strip():
            return False
        try:
            with client.open(url, timeout=10) as response:
                html = response.read(1024 * 1024).decode("utf-8", errors="replace")
                return response.status == 200 and escape(expected) in html
        except (URLError, TimeoutError, OSError):
            return False
