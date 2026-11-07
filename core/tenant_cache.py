"""Cache de contexto institucional sem transformar Redis em fonte de autorização.

Os loaders recebem a responsabilidade de consultar o PostgreSQL e aplicar as
regras de visibilidade. O Redis apenas acelera o resultado já autorizado.
"""

import logging
from typing import Any, Callable, Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TenantLoader = Callable[[], Any]


def _normalize_hostname(hostname: str) -> str:
    """Normaliza host para evitar chaves duplicadas e cache poisoning básico."""
    return hostname.strip().lower().rstrip(".").split(":", 1)[0]


def _safe_get(key: str) -> Any:
    try:
        return cache.get(key)
    except Exception:
        logger.warning("Falha ao ler cache institucional", extra={"cache_key": key})
        return None


def _safe_set(key: str, value: Any, timeout: int) -> None:
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        logger.warning("Falha ao gravar cache institucional", extra={"cache_key": key})


def _safe_delete(key: str) -> None:
    try:
        cache.delete(key)
    except Exception:
        logger.warning("Falha ao invalidar cache institucional", extra={"cache_key": key})


def _load(key: str, loader: TenantLoader, timeout: int) -> Any:
    """Retorna cache hit ou consulta o loader e grava a projeção derivada."""
    cached = _safe_get(key)
    if cached is not None:
        return cached

    value = loader()
    if value is not None:
        _safe_set(key, value, timeout)
    return value


def tenant_key(hostname: str) -> str:
    return f"tenant:hostname:{_normalize_hostname(hostname)}"


def branding_key(organization_id: int | str) -> str:
    return f"tenant:{organization_id}:branding"


def public_config_key(organization_id: int | str) -> str:
    return f"tenant:{organization_id}:public-config"


def get_organization_id(hostname: str, loader: TenantLoader) -> Any:
    """Resolve hostname para organização com TTL e fallback ao PostgreSQL."""
    return _load(
        tenant_key(hostname),
        loader,
        getattr(settings, "TENANT_CACHE_TTL", 300),
    )


def get_branding(organization_id: int | str, loader: TenantLoader) -> Any:
    """Obtém branding por organização, nunca por chave global."""
    return _load(
        branding_key(organization_id),
        loader,
        getattr(settings, "TENANT_BRANDING_CACHE_TTL", 300),
    )


def get_public_config(organization_id: int | str, loader: TenantLoader) -> Any:
    """Obtém somente configuração pública carregada pelo loader autorizado.

    O loader deve consultar o PostgreSQL e excluir dados privados. Este helper
    não participa de decisões de permissão nem deve ser usado para autorizá-las.
    """
    return _load(
        public_config_key(organization_id),
        loader,
        getattr(settings, "TENANT_PUBLIC_CONFIG_CACHE_TTL", 120),
    )


def invalidate_tenant_cache(
    *,
    hostname: Optional[str] = None,
    organization_id: Optional[int | str] = None,
) -> None:
    """Invalida as projeções afetadas por mudança de domínio ou branding."""
    if hostname:
        _safe_delete(tenant_key(hostname))
    if organization_id is not None:
        _safe_delete(branding_key(organization_id))
        _safe_delete(public_config_key(organization_id))
