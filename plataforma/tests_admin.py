from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ConviteOrganizacao, DominioOrganizacao, MembroOrganizacao, Organizacao


User = get_user_model()


class AdminInstitucionalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Senha-forte-123",
        )
        self.client.force_login(self.admin)
        self.organizacao = Organizacao.objects.create(slug="camppg", nome="CAMPPG")

    def test_admin_home_uses_clear_platform_heading(self):
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Palácio Mental — Operação da Plataforma")
        self.assertContains(response, "O que você precisa fazer?")
        self.assertContains(response, "Preparar um ambiente institucional")
        self.assertContains(response, "Controlar quem entra")
        self.assertContains(response, "Operar projetos")
        self.assertContains(response, "Revisar e corrigir")
        self.assertContains(response, "Ver todos os modelos técnicos")

    def test_organization_changelist_shows_operational_columns(self):
        response = self.client.get(reverse("admin:listaEspera_organizacao_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CAMPPG")
        self.assertContains(response, "Domínios")
        self.assertContains(response, "Membros")
        self.assertContains(response, "Ativa")

    def test_organization_form_exposes_identity_and_domains_as_sections(self):
        response = self.client.get(reverse("admin:listaEspera_organizacao_change", args=[self.organizacao.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identificação da organização")
        self.assertContains(response, "Identidade exibida")
        self.assertContains(response, "Domínios das organizações")
        self.assertContains(response, "Hostname")

    def test_invitation_generates_technical_token_and_auditor(self):
        response = self.client.post(
            reverse("admin:listaEspera_conviteorganizacao_add"),
            {
                "organizacao": str(self.organizacao.pk),
                "email": "professor@example.com",
                "papel": MembroOrganizacao.PAPEL_PROFESSOR,
                "status": ConviteOrganizacao.STATUS_PENDENTE,
                "expira_em_0": (timezone.now() + timedelta(days=7)).strftime("%d/%m/%Y"),
                "expira_em_1": "12:00:00",
                "_save": "Salvar",
            },
        )

        self.assertEqual(response.status_code, 302)
        convite = ConviteOrganizacao.objects.get(email="professor@example.com")
        self.assertEqual(len(convite.hash_token), 64)
        self.assertEqual(convite.convidado_por_id, self.admin.pk)

    def test_domain_form_normalizes_hostname(self):
        response = self.client.post(
            reverse("admin:listaEspera_dominioorganizacao_add"),
            {
                "organizacao": str(self.organizacao.pk),
                "hostname": "CAMPPG.PALACIOMENTAL.COM.BR.",
                "tipo": DominioOrganizacao.TIPO_SUBDOMINIO,
                "principal": "on",
                "status_verificacao": "ativo",
                "_save": "Salvar",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(DominioOrganizacao.objects.filter(hostname="camppg.palaciomental.com.br").exists())
