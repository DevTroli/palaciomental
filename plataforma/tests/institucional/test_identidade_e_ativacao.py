from django.contrib.auth import get_user_model

from plataforma.models import DominioOrganizacao, IdentidadeOrganizacao, MembroOrganizacao, Organizacao
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
