"""PM-05: convites só valem no endereço institucional da organização."""

import hashlib
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from plataforma.models import (
    ConviteGrupo,
    ConviteOrganizacao,
    DominioOrganizacao,
    Grupo,
    MembroGrupo,
    MembroOrganizacao,
    Organizacao,
    ProgramaInstitucional,
    Turma,
)

User = get_user_model()

HOST_A = "camppg.palaciomental.com.br"
HOST_B = "outra.palaciomental.com.br"
HOST_GLOBAL = "palaciomental.com.br"


@override_settings(
    ALLOWED_HOSTS=["testserver", ".palaciomental.com.br"],
    PALACIO_BASE_DOMAIN="palaciomental.com.br",
    TENANT_RESERVED_HOSTS=["www", "api", "status", "admin", "app"],
)
class ConviteSomenteNoHostDaOrganizacaoTests(TestCase):
    def setUp(self):
        self.org_a = Organizacao.objects.create(slug="camppg", nome="CAMPPG", status=Organizacao.STATUS_ATIVA)
        self.org_b = Organizacao.objects.create(slug="outra", nome="Outra", status=Organizacao.STATUS_ATIVA)
        DominioOrganizacao.objects.create(organizacao=self.org_a, hostname=HOST_A, principal=True)
        DominioOrganizacao.objects.create(organizacao=self.org_b, hostname=HOST_B, principal=True)
        self.gestor = User.objects.create_user(username="gestor", email="gestor@example.com", password="Senha-forte-123")
        MembroOrganizacao.objects.create(organizacao=self.org_a, usuario=self.gestor, papel=MembroOrganizacao.PAPEL_GESTOR)
        self.convidado = User.objects.create_user(username="convidado", email="convidado@example.com", password="Senha-forte-123")
        # O convidado já é membro de B para alcançar o host B; o convite é de A.
        MembroOrganizacao.objects.create(organizacao=self.org_b, usuario=self.convidado, papel=MembroOrganizacao.PAPEL_MEMBRO)

        programa = ProgramaInstitucional.objects.create(
            organizacao=self.org_a, nome="Programa A", slug="programa-a",
            status=ProgramaInstitucional.STATUS_PUBLICADO, criado_por=self.gestor,
        )
        turma = Turma.objects.create(programa=programa, nome="Turma A", criado_por=self.gestor)
        self.grupo = Grupo.objects.create(turma=turma, nome="Grupo A", criado_por=self.gestor)

        self.token_grupo = "token-grupo-pm05"
        ConviteGrupo.objects.create(
            grupo=self.grupo, convidado_por=self.gestor, email=self.convidado.email,
            hash_token=hashlib.sha256(self.token_grupo.encode()).hexdigest(),
            expira_em=timezone.now() + timedelta(days=7),
        )
        self.token_org = "token-org-pm05"
        ConviteOrganizacao.objects.create(
            organizacao=self.org_a, convidado_por=self.gestor, email=self.convidado.email,
            papel=MembroOrganizacao.PAPEL_MEMBRO,
            hash_token=hashlib.sha256(self.token_org.encode()).hexdigest(),
            expira_em=timezone.now() + timedelta(days=7),
        )
        self.client.force_login(self.convidado)

    def _url(self, nome, token):
        return reverse(f"plataforma:{nome}", kwargs={"token": token})

    def _casos(self):
        return (
            ("institutional_invite_accept", self.token_grupo),
            ("institutional_organization_invite_accept", self.token_org),
        )

    def _assert_sem_efeito(self):
        self.assertFalse(MembroOrganizacao.objects.filter(organizacao=self.org_a, usuario=self.convidado).exists())
        self.assertFalse(MembroGrupo.objects.filter(grupo=self.grupo, usuario=self.convidado).exists())
        self.assertEqual(ConviteGrupo.objects.get().status, ConviteGrupo.STATUS_PENDENTE)
        self.assertEqual(ConviteOrganizacao.objects.get().status, ConviteOrganizacao.STATUS_PENDENTE)

    def test_host_de_outra_organizacao_responde_404_sem_efeito(self):
        for nome, token in self._casos():
            with self.subTest(view=nome):
                response = self.client.get(self._url(nome, token), HTTP_HOST=HOST_B)
                self.assertEqual(response.status_code, 404)
        self._assert_sem_efeito()

    def test_host_global_responde_404_sem_efeito(self):
        for nome, token in self._casos():
            with self.subTest(view=nome):
                response = self.client.get(self._url(nome, token), HTTP_HOST=HOST_GLOBAL)
                self.assertEqual(response.status_code, 404)
        self._assert_sem_efeito()

    def test_token_inexistente_responde_404(self):
        for nome, _ in self._casos():
            with self.subTest(view=nome):
                response = self.client.get(self._url(nome, "nao-existe"), HTTP_HOST=HOST_A)
                self.assertEqual(response.status_code, 404)

    def test_host_correto_aceita_convite_de_organizacao(self):
        response = self.client.post(self._url("institutional_organization_invite_accept", self.token_org), {"action": "accept"}, HTTP_HOST=HOST_A)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MembroOrganizacao.objects.filter(organizacao=self.org_a, usuario=self.convidado).exists())
        self.assertEqual(ConviteOrganizacao.objects.get().status, ConviteOrganizacao.STATUS_ACEITO)

    def test_host_correto_aceita_convite_de_grupo(self):
        response = self.client.post(self._url("institutional_invite_accept", self.token_grupo), {"action": "accept"}, HTTP_HOST=HOST_A)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MembroGrupo.objects.filter(grupo=self.grupo, usuario=self.convidado).exists())
        self.assertEqual(ConviteGrupo.objects.get().status, ConviteGrupo.STATUS_ACEITO)
