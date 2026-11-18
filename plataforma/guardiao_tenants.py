"""Publica um retrato dos domínios ativos usando a conexão autenticada do worker."""
import json
from urllib.request import Request

from .branding import organization_branding
from .models import DominioOrganizacao, Organizacao
from .rls import system_context


def sincronizar_tenants(endpoint, token, opener):
    with system_context():
        domains = DominioOrganizacao.objects.filter(
            status_verificacao="ativo", organizacao__status=Organizacao.STATUS_ATIVA,
        ).select_related("organizacao__identidade").order_by("organizacao_id", "-principal", "hostname")
        selected = {}
        for domain in domains.iterator():
            organization_id = str(domain.organizacao_id)
            if organization_id in selected:
                continue
            organization = domain.organizacao
            identity = getattr(organization, "identidade", None)
            display_name = getattr(identity, "nome_exibicao", "").strip()
            selected[organization_id] = {
                "hostname": domain.hostname.lower(),
                "slug": organization.slug,
                "displayName": display_name or organization.nome,
            }
            if identity is not None:
                branding = organization_branding(organization)
                selected[organization_id].update(
                    primaryColor=branding["tenant_primary_color"],
                    accentColor=branding["tenant_accent_color"],
                )
    payload = {"tenants": [{"organizationId": key, **tenant} for key, tenant in selected.items()]}
    request = Request(endpoint.removesuffix("/links") + "/tenants", method="PUT",
                      data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={
                          "Authorization": f"Bearer {token}", "Content-Type": "application/json",
                      })
    with opener.open(request, timeout=10) as response:
        if response.status != 204:
            raise ValueError("Não foi possível sincronizar organizações monitoradas.")
