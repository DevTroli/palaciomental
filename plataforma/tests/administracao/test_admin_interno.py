from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from plataforma.models import ConviteOrganizacao, MembroOrganizacao, Organizacao


User = get_user_model()


class AdminInstitucionalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Senha-forte-123",
        )
        self.client.force_login(self.admin)
        self.organizacao = Organizacao.objects.create(slug="camppg", nome="CAMPPG", status=Organizacao.STATUS_ATIVA)


    def test_staff_without_internal_group_cannot_access_django_admin(self):
        gestor = User.objects.create_user(
            username="gestor-camppg",
            email="gestor@camppg.example",
            password="Senha-forte-123",
            is_staff=True,
        )
        self.client.force_login(gestor)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "exclusiva da equipe interna", status_code=403)

    def test_internal_group_can_access_django_admin(self):
        equipe = Group.objects.create(name="Equipe PM")
        membro_pm = User.objects.create_user(
            username="operador-pm",
            email="operador@palaciomental.example",
            password="Senha-forte-123",
            is_staff=True,
        )
        membro_pm.groups.add(equipe)
        self.client.force_login(membro_pm)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)


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
