from django.test import Client
from django.urls import reverse

from plataforma.models import MembroOrganizacao, MembroTurma, ProgramaInstitucional, Project, Turma

from .base import PortalInstitucionalBase


class JornadasStatusTests(PortalInstitucionalBase):
    def test_member_signs_in_and_reads_projects_programs_and_classes(self):
        MembroOrganizacao.objects.create(
            organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO,
        )
        project = Project.objects.create(
            owner=self.user, organizacao=self.organization, title="Projeto da jornada",
            direction="Projeto de teste", visibility=Project.VISIBILITY_PUBLIC,
        )
        program = ProgramaInstitucional.objects.create(
            organizacao=self.organization, nome="Programa da jornada", slug="programa-jornada",
            status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user,
        )
        turma = Turma.objects.create(
            programa=program, nome="Turma da jornada", criado_por=self.user,
        )
        MembroTurma.objects.create(turma=turma, usuario=self.user)
        client = Client(enforce_csrf_checks=True)
        host = "camppg.palaciomental.com.br"
        request = {"HTTP_HOST": host, "secure": True}
        login = reverse("plataforma:login")

        self.assertContains(client.get(login, **request), 'data-status-probe="organizacao"')
        response = client.post(login, {
            "username": self.user.username,
            "password": "Senha-forte-123",
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        }, HTTP_REFERER=f"https://{host}{login}", **request)
        self.assertRedirects(response, reverse("core:index"), fetch_redirect_response=False)

        for route, expected in (
            (reverse("plataforma:project_detail", args=[project.pk]), project.title),
            (reverse("plataforma:institutional_programs"), program.nome),
            (reverse("plataforma:institutional_program_detail", args=[program.pk]), turma.nome),
        ):
            with self.subTest(route=route):
                self.assertContains(client.get(route, **request), expected)

    def test_probe_reports_each_read_and_rejects_invalid_credentials(self):
        from http.cookiejar import Cookie
        from io import BytesIO, StringIO
        from unittest.mock import patch
        from urllib.error import HTTPError
        from urllib.parse import urlsplit

        from django.core.management import call_command, CommandError
        from plataforma.management.commands import verificar_jornadas_institucionais as probe

        MembroOrganizacao.objects.create(
            organizacao=self.organization, usuario=self.user, papel=MembroOrganizacao.PAPEL_MEMBRO,
        )
        project = Project.objects.create(
            owner=self.user, organizacao=self.organization, title="Projeto da sondagem",
            direction="Projeto de teste", visibility=Project.VISIBILITY_PUBLIC,
        )
        program = ProgramaInstitucional.objects.create(
            organizacao=self.organization, nome="Programa da sondagem", slug="programa-sondagem",
            status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.user,
        )
        turma = Turma.objects.create(programa=program, nome="Turma da sondagem", criado_por=self.user)
        MembroTurma.objects.create(turma=turma, usuario=self.user)

        def transport(_redirect_handler, cookie_handler):
            client = Client(enforce_csrf_checks=True)

            class TestTransport:
                def open(self, request, timeout):
                    address = urlsplit(request if isinstance(request, str) else request.full_url)
                    path = address.path + ("?" + address.query if address.query else "")
                    params = {"HTTP_HOST": address.netloc, "secure": True}
                    if isinstance(request, str):
                        response = client.get(path, **params)
                    else:
                        response = client.post(path, request.data, content_type="application/x-www-form-urlencoded",
                                               HTTP_REFERER=request.get_header("Referer"), **params)
                    csrf = client.cookies.get("csrftoken")
                    if csrf:
                        cookie_handler.cookiejar.set_cookie(Cookie(
                            0, "csrftoken", csrf.value, None, False, address.hostname,
                            False, False, "/", True, True, None, True, None, None, {},
                        ))
                    if response.status_code != 200:
                        raise HTTPError(address.geturl(), response.status_code, "", response.headers,
                                        BytesIO(response.content))
                    body = BytesIO(response.content)
                    body.status = response.status_code
                    return body

            return TestTransport()

        options = {
            "origem": "https://camppg.palaciomental.com.br",
            "projeto": project.pk,
            "titulo_projeto": project.title,
            "programa": str(program.pk),
            "nome_turma": turma.nome,
        }
        cases = (
            ("Senha-forte-123", turma.nome, {"login": True, "projetos": True, "programas_e_turmas": True}),
            ("Senha-forte-123", "Turma inexistente", {"login": True, "projetos": True, "programas_e_turmas": False}),
            ("senha-incorreta", turma.nome, {"login": False, "projetos": False, "programas_e_turmas": False}),
        )
        import json
        for password, class_name, expected in cases:
            with self.subTest(expected=expected):
                output = StringIO()
                with patch.object(probe, "build_opener", side_effect=transport), patch.dict(
                    "os.environ", {"PM_PROBE_USERNAME": self.user.username, "PM_PROBE_PASSWORD": password},
                ):
                    args = {**options, "nome_turma": class_name, "stdout": output}
                    if all(expected.values()):
                        call_command("verificar_jornadas_institucionais", **args)
                    else:
                        with self.assertRaises(CommandError):
                            call_command("verificar_jornadas_institucionais", **args)
                self.assertEqual(json.loads(output.getvalue()), expected)
