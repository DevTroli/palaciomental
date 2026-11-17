import json
from unittest.mock import MagicMock, patch

from django.test import TestCase

from plataforma.guardiao_tenants import sincronizar_tenants
from plataforma.models import DominioOrganizacao, Organizacao


class TenantSnapshotTests(TestCase):
    def test_snapshot_prefers_primary_and_removes_suspended_organizations(self):
        active = Organizacao.objects.create(nome="Ativa", slug="ativa", status="ativa")
        suspended = Organizacao.objects.create(nome="Suspensa", slug="suspensa", status="suspensa")
        DominioOrganizacao.objects.create(organizacao=active, hostname="secondary.example.org")
        DominioOrganizacao.objects.create(organizacao=active, hostname="primary.example.org", principal=True)
        DominioOrganizacao.objects.create(organizacao=suspended, hostname="suspended.example.org", principal=True)
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.status = 204
        with patch("plataforma.guardiao_tenants.system_context"):
            sincronizar_tenants("https://api.example.org/v1/guardiao/links", "test-token", opener)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.method, "PUT")
        self.assertEqual(json.loads(request.data), {"tenants": [
            {"organizationId": str(active.pk), "hostname": "primary.example.org"},
        ]})
        active.status = "suspensa"
        active.save()
        with patch("plataforma.guardiao_tenants.system_context"):
            sincronizar_tenants("https://api.example.org/v1/guardiao/links", "test-token", opener)
        self.assertEqual(json.loads(opener.open.call_args.args[0].data), {"tenants": []})
