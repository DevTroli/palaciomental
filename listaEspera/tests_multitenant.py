from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from .models import (
    ConviteOrganizacao,
    DominioOrganizacao,
    IdentidadeOrganizacao,
    MembroOrganizacao,
    Organizacao,
    Project,
)


User = get_user_model()


class OrganizacaoModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="Senha-forte-123",
        )
        self.organization = Organizacao.objects.create(
            slug="camppg",
            nome="CAMPPG",
            nome_legal="CAMPPG — Centro de Apoio",
        )

    def test_organization_entities_are_created_with_uuid_keys(self):
        identity = IdentidadeOrganizacao.objects.create(
            organizacao=self.organization,
            nome_exibicao="CAMPPG",
            cor_primaria="#321943",
        )
        domain = DominioOrganizacao.objects.create(
            organizacao=self.organization,
            hostname="camppg.palaciomental.com.br",
            principal=True,
        )
        affiliation = MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.owner,
            papel=MembroOrganizacao.PAPEL_PROPRIETARIO,
        )
        invitation = ConviteOrganizacao.objects.create(
            organizacao=self.organization,
            convidado_por=self.owner,
            email="professor@example.com",
            papel=MembroOrganizacao.PAPEL_PROFESSOR,
            hash_token="a" * 64,
            expira_em=timezone.now() + timedelta(days=7),
        )

        self.assertEqual(len(str(self.organization.pk)), 36)
        self.assertEqual(identity.organizacao_id, self.organization.pk)
        self.assertEqual(domain.organizacao_id, self.organization.pk)
        self.assertEqual(affiliation.status, MembroOrganizacao.STATUS_ATIVA)
        self.assertEqual(invitation.status, ConviteOrganizacao.STATUS_PENDENTE)

    def test_affiliation_is_unique_per_user_and_organization(self):
        MembroOrganizacao.objects.create(
            organizacao=self.organization,
            usuario=self.owner,
            papel=MembroOrganizacao.PAPEL_PROPRIETARIO,
        )

        with self.assertRaises(IntegrityError):
            MembroOrganizacao.objects.create(
                organizacao=self.organization,
                usuario=self.owner,
                papel=MembroOrganizacao.PAPEL_GESTOR,
            )

    def test_project_can_remain_personal_or_be_scoped_to_organization(self):
        personal = Project.objects.create(
            owner=self.owner,
            title="Projeto pessoal",
            direction="Direção pessoal",
            category="Pesquisa",
        )
        institutional = Project.objects.create(
            owner=self.owner,
            organizacao=self.organization,
            title="Projeto CAMPPG",
            direction="Direção institucional",
            category="Educação",
        )

        self.assertIsNone(personal.organizacao_id)
        self.assertEqual(institutional.organizacao_id, self.organization.pk)
