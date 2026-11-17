"""Publica um retrato dos domínios ativos usando a conexão autenticada do worker."""
import json
from urllib.request import Request

from .models import DominioOrganizacao, Organizacao
from .rls import system_context


def sincronizar_tenants(endpoint, token, opener):
    with system_context():
        domains = DominioOrganizacao.objects.filter(
            status_verificacao="ativo", organizacao__status=Organizacao.STATUS_ATIVA,
        ).order_by("organizacao_id", "-principal", "hostname")
        selected = {}
        for domain in domains.iterator():
            selected.setdefault(str(domain.organizacao_id), domain.hostname.lower())
    payload = {"tenants": [{"organizationId": key, "hostname": host} for key, host in selected.items()]}
    request = Request(endpoint.removesuffix("/links") + "/tenants", method="PUT",
                      data=json.dumps(payload).encode(), headers={
                          "Authorization": f"Bearer {token}", "Content-Type": "application/json",
                      })
    with opener.open(request, timeout=10) as response:
        if response.status != 204:
            raise ValueError("Não foi possível sincronizar organizações monitoradas.")
