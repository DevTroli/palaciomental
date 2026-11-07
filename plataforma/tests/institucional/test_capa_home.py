from typing import cast
from django.db.models.fields.files import ImageFieldFile

from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.test import override_settings
from django.template.loader import render_to_string
from django.test.client import RequestFactory

from plataforma.branding import invitation_branding
from plataforma.models import (
    DominioOrganizacao, IdentidadeOrganizacao, MembroOrganizacao, Organizacao,
    ProgramaInstitucional, Project, Turma, VinculoProjetoInstitucional,
)
from plataforma.validators import validar_capa
from .base import PortalInstitucionalBase

HOST = "camppg.palaciomental.com.br"


class CapaHomeTests(PortalInstitucionalBase):
    def setUp(self):
        super().setUp()
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.identity = IdentidadeOrganizacao.objects.create(organizacao=self.organization)
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user, papel="gestor")
        self.client.force_login(self.user)

    def test_cover_normalization_unique_key_and_removal(self):
        self.identity.capa = self.logo_file("capa.png", (3200, 1000))
        self.identity.save()
        self.assertEqual(cast(ImageFieldFile, self.identity.capa).width, 2400)
        key = self.identity.capa.name
        assert key is not None
        self.assertIn(f"tenants/{self.organization.pk}/branding/cover/", key)
        self.identity.capa = self.logo_file("nova.png", (1000, 400))
        self.identity.save()
        self.assertNotEqual(self.identity.capa.name, key)
        response = self.client.post("/gestao/identidade/", {
            "nome_exibicao": "Campus", "capa-clear": "on",
        }, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 302)
        self.identity.refresh_from_db()
        self.assertFalse(self.identity.capa)

    def test_rejects_invalid_cover(self):
        for file in (
            self.logo_file("small.png", (100, 100)),
            self.logo_file("portrait.png", (640, 900)),
            self.logo_file("bad.svg", (1000, 400)),
        ):
            with self.assertRaises(ValidationError):
                validar_capa(file)

    def test_cover_upload_and_presentation_escaped(self):
        response = self.client.post("/gestao/identidade/", {
            "nome_exibicao": "Meu campus", "apresentacao": "<script>alert(1)</script>",
            "capa": self.logo_file("capa.png", (1200, 400)),
        }, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 302)
        response = self.client.get("/", HTTP_HOST=HOST)
        self.assertContains(response, "/branding/cover/")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_empty_cover_and_home_sections(self):
        response = self.client.get("/", HTTP_HOST=HOST)
        for label in ("tenant-cover--empty", "Projetos autônomos", "Projetos vinculados", "Programas ativos", "Turmas elegíveis"):
            self.assertContains(response, label)

    def test_only_tenant_public_projects_in_columns(self):
        autonomous = Project.objects.create(title="Autônomo A", owner=self.user, organizacao=self.organization, visibility=Project.VISIBILITY_PUBLIC)
        linked = Project.objects.create(title="Vinculado A", owner=self.user, organizacao=self.organization, visibility=Project.VISIBILITY_PUBLIC)
        Project.objects.create(title="Privado A secreto", owner=self.user, organizacao=self.organization, visibility=Project.VISIBILITY_PRIVATE)
        other = Organizacao.objects.create(slug="outro", nome="Outro", status="ativa")
        Project.objects.create(title="Outro tenant secreto", owner=self.user, organizacao=other, visibility=Project.VISIBILITY_PUBLIC)
        program = ProgramaInstitucional.objects.create(organizacao=self.organization, nome="Programa", criado_por=self.user)
        turma = Turma.objects.create(programa=program, nome="Turma", criado_por=self.user)
        VinculoProjetoInstitucional.objects.create(projeto=linked, turma=turma, vinculado_por=self.user)
        response = self.client.get("/", HTTP_HOST=HOST)
        self.assertEqual(list(response.context["projetos_autonomos"]), [autonomous])
        self.assertEqual(list(response.context["projetos_vinculados"]), [linked])
        self.assertNotContains(response, "Privado A secreto")
        self.assertNotContains(response, "Outro tenant secreto")

    def test_theme_and_cover_do_not_leak_to_other_tenant(self):
        self.identity.capa = self.logo_file("capa.png", (1200, 400))
        self.identity.tema = {"primary": "#ABCDEF"}
        self.identity.save()
        other = Organizacao.objects.create(slug="outro", nome="Outro", status="ativa")
        DominioOrganizacao.objects.create(organizacao=other, hostname="outro.palaciomental.com.br", principal=True)
        MembroOrganizacao.objects.create(organizacao=other, usuario=self.user)
        response = self.client.get("/", HTTP_HOST="outro.palaciomental.com.br")
        self.assertNotContains(response, cast(ImageFieldFile, self.identity.capa).url)
        self.assertNotContains(response, "#ABCDEF")

    def test_email_uses_absolute_cover_and_shared_colors(self):
        self.identity.capa = self.logo_file("capa.png", (1200, 400))
        self.identity.tema = {"secondary": "#123456"}
        self.identity.save()
        request = RequestFactory().get("/", secure=True, HTTP_HOST=HOST)
        branding = invitation_branding(request, self.organization)
        html = render_to_string("emails/invitation_base.html", branding)
        self.assertIn(f"https://{HOST}/media/", html)
        self.assertIn("#123456", html)

    def test_professor_cannot_upload_cover(self):
        membership = MembroOrganizacao.objects.get(organizacao=self.organization, usuario=self.user)
        membership.papel = "professor"
        membership.save()
        response = self.client.post("/gestao/identidade/", {
            "capa": self.logo_file("capa.png", (1200, 400)),
        }, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 403)
        self.identity.refresh_from_db()
        self.assertFalse(self.identity.capa)

    def test_logo_replacement_uses_new_key_for_immutable_cache(self):
        self.identity.logo = self.logo_file("marca.png")
        self.identity.save()
        original = self.identity.logo.name
        self.identity.logo = self.logo_file("marca.png")
        self.identity.save()
        self.assertNotEqual(self.identity.logo.name, original)
        key = self.identity.logo.name
        assert key is not None
        self.assertIn(f"tenants/{self.organization.pk}/branding/logo/", key)
