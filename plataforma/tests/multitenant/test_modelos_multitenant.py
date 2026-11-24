from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from plataforma.models import MembroOrganizacao, Organizacao


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
            status=Organizacao.STATUS_ATIVA,
        )


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
