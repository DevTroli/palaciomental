import hashlib
from io import BytesIO
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from plataforma.models import ConviteGrupo, ConviteOrganizacao, DominioOrganizacao, Grupo, IdentidadeOrganizacao, MembroGrupo, MembroOrganizacao, MembroTurma, Organizacao, ProgramaInstitucional, Project, SolicitacaoGrupo, SolicitacaoTurma, Turma, VinculoProjetoInstitucional
from plataforma.services import ativar_organizacao


User = get_user_model()


from .base import PortalInstitucionalBase


class IdentidadeEAtivacaoTests(PortalInstitucionalBase):
    def test_logo_is_validated_and_saved_under_tenant_path(self):
        identidade = IdentidadeOrganizacao.objects.create(
            organizacao=self.organization,
            logo=self.logo_file(),
            cor_primaria="roxo-institucional",
            cor_destaque="verde-institucional",
            cor_fundo="bege-claro",
        )
        self.assertTrue(identidade.completa)
        self.assertIn(f"tenants/{self.organization.pk}/branding/logo/", str(identidade.logo.name))

    def test_logo_is_normalized_before_storage(self):
        identidade = IdentidadeOrganizacao.objects.create(
            organizacao=self.organization,
            logo=self.logo_file("large-logo.jpg", size=(2000, 1200), image_format="JPEG"),
            cor_primaria="roxo-institucional",
            cor_destaque="verde-institucional",
            cor_fundo="bege-claro",
        )
        identidade.logo.open()
        with Image.open(identidade.logo) as imagem:
            self.assertLessEqual(max(imagem.size), 1600)
            self.assertEqual(imagem.format, "JPEG")

    def test_invalid_logo_format_is_rejected(self):
        identidade = IdentidadeOrganizacao(
            organizacao=self.organization,
            logo=SimpleUploadedFile("logo.gif", b"not-an-image", content_type="image/gif"),
        )
        with self.assertRaises(ValidationError):
            identidade.full_clean()

    def test_logo_over_two_megabytes_is_rejected(self):
        identidade = IdentidadeOrganizacao(
            organizacao=self.organization,
            logo=SimpleUploadedFile("logo.png", b"x" * (2 * 1024 * 1024 + 1), content_type="image/png"),
        )
        with self.assertRaisesMessage(ValidationError, "no máximo 2 MB"):
            identidade.full_clean()

    def test_organization_activation_requires_identity_domain_and_owner(self):
        self.organization.status = Organizacao.STATUS_CONFIGURANDO
        self.organization.save(update_fields=["status"])
        with self.assertRaisesMessage(Exception, "Configure a logo"):
            ativar_organizacao(self.organization, executor=self.pm_staff)

        IdentidadeOrganizacao.objects.create(
            organizacao=self.organization,
            logo=self.logo_file(),
            cor_primaria="roxo-institucional",
            cor_destaque="verde-institucional",
            cor_fundo="bege-claro",
        )
        DominioOrganizacao.objects.filter(organizacao=self.organization).delete()
        with self.assertRaisesMessage(Exception, "domínio principal"):
            ativar_organizacao(self.organization, executor=self.pm_staff)

        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_PROPRIETARIO,
        )
        DominioOrganizacao.objects.create(
            organizacao=self.organization,
            hostname="camppg.palaciomental.com.br",
            principal=True,
            status_verificacao="ativo",
        )
        with self.assertRaisesMessage(Exception, "Somente a equipe"):
            ativar_organizacao(self.organization, executor=self.user)
        self.assertEqual(self.organization.status, Organizacao.STATUS_CONFIGURANDO)

    def test_configured_organization_can_be_activated_by_staff(self):
        self.organization.status = Organizacao.STATUS_CONFIGURANDO
        self.organization.save(update_fields=["status"])
        IdentidadeOrganizacao.objects.create(
            organizacao=self.organization,
            logo=self.logo_file(),
            cor_primaria="roxo-institucional",
            cor_destaque="verde-institucional",
            cor_fundo="bege-claro",
        )
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.user,
            papel=MembroOrganizacao.PAPEL_PROPRIETARIO,
        )
        ativar_organizacao(self.organization, executor=self.pm_staff)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.status, Organizacao.STATUS_ATIVA)
