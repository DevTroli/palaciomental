from typing import cast
from django.db.models.fields.files import ImageFieldFile

from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.test import override_settings

from plataforma.models import DominioOrganizacao, IdentidadeOrganizacao, MembroOrganizacao, Organizacao
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
