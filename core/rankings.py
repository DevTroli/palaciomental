"""Projeções de relevância em Redis Sorted Sets.

PostgreSQL continua sendo a fonte oficial. Este módulo só grava projeções
reconstruíveis depois de uma transação confirmada.
"""

import logging
from datetime import timedelta
from typing import Iterable, Optional

import redis
from django.conf import settings
from django.utils import timezone

from plataforma.models import Project, ProjectVote

logger = logging.getLogger(__name__)

PERIODS = {"all": None, "weekly": timedelta(days=7), "monthly": timedelta(days=30)}


def ranking_key(period: str = "all", tenant_id: Optional[int | str] = None) -> str:
    if period not in PERIODS:
        raise ValueError(f"Período inválido: {period}")
    scope = "global" if tenant_id is None else f"tenant:{tenant_id}"
    return f"ranking:{scope}:{period}"


def _redis_client():
    url = getattr(settings, "REDIS_URL", "")
    if not url:
        return None
    return redis.Redis.from_url(url, decode_responses=True)


def _safe(operation, *args, **kwargs):
    client = _redis_client()
    if client is None:
        return None
    try:
        return operation(client, *args, **kwargs)
    except Exception:
        logger.warning("Falha na projeção de ranking Redis")
        return None


def _zadd(client, key, project_id, score):
    return client.zadd(key, {str(project_id): score})


def _zrem(client, key, project_id):
    return client.zrem(key, str(project_id))


def _zincrby(client, key, project_id, delta):
    return client.zincrby(key, delta, str(project_id))


def _vote_count(project_id: int, period: str) -> int:
    votes = ProjectVote.objects.filter(project_id=project_id)
    cutoff = PERIODS[period]
    if cutoff is not None:
        votes = votes.filter(created_at__gte=timezone.now() - cutoff)
    return votes.count()


def project_is_public(project_id: int) -> bool:
    return Project.objects.filter(
        pk=project_id, visibility=Project.VISIBILITY_PUBLIC
    ).exists()


def project_tenant_id(project_id: int) -> Optional[str]:
    """Resolve o tenant oficial do projeto sem usar Redis como autorização."""
    return Project.objects.filter(pk=project_id).values_list("organizacao_id", flat=True).first()


def update_project_projection(
    project_id: int,
    *,
    delta: Optional[int] = None,
    tenant_id: Optional[int | str] = None,
) -> None:
    """Atualiza rankings após commit; sem delta, recalcula a pontuação oficial.

    Recalcular é intencional: torna a operação idempotente e corrige qualquer
    divergência sem duplicar pontuação. O parâmetro delta existe para eventos,
    mas a integração atual usa a contagem do PostgreSQL como fonte oficial.
    """
    public = project_is_public(project_id)
    tenant_id = tenant_id if tenant_id is not None else project_tenant_id(project_id)
    scopes = [(None, "global")]
    if tenant_id is not None:
        scopes.append((tenant_id, f"tenant:{tenant_id}"))

    def apply(client, scope_id):
        for period in PERIODS:
            key = ranking_key(period, scope_id)
            if not public:
                _zrem(client, key, project_id)
                continue
            _zadd(client, key, project_id, _vote_count(project_id, period))

    client = _redis_client()
    if client is None:
        return
    try:
        for scope_id, _ in scopes:
            apply(client, scope_id)
    except Exception:
        logger.warning("Falha ao atualizar projeção de ranking", extra={"project_id": project_id})


def adjust_project_projection(
    project_id: int,
    delta: int,
    *,
    tenant_id: Optional[int | str] = None,
    occurred_at=None,
) -> None:
    """Aplica o delta de um voto confirmado usando ZINCRBY.

    O chamador deve registrar esta função com ``transaction.on_commit``. A
    unicidade SQL de ProjectVote impede que um mesmo voto gere dois deltas.
    """
    if delta == 0 or not project_is_public(project_id):
        return
    tenant_id = tenant_id if tenant_id is not None else project_tenant_id(project_id)
    scopes = [None] if tenant_id is None else [None, tenant_id]
    client = _redis_client()
    if client is None:
        return
    try:
        for scope_id in scopes:
            for period in PERIODS:
                cutoff = PERIODS[period]
                if occurred_at is not None and cutoff is not None and occurred_at < timezone.now() - cutoff:
                    continue
                _zincrby(client, ranking_key(period, scope_id), project_id, delta)
    except Exception:
        logger.warning("Falha ao aplicar delta no ranking", extra={"project_id": project_id, "delta": delta})


def remove_project_from_rankings(project_id: int, tenant_id: Optional[int | str] = None) -> None:
    client = _redis_client()
    if client is None:
        return
    scopes = [None] if tenant_id is None else [None, tenant_id]
    try:
        for scope_id in scopes:
            for period in PERIODS:
                _zrem(client, ranking_key(period, scope_id), project_id)
    except Exception:
        logger.warning("Falha ao remover projeto dos rankings", extra={"project_id": project_id})


def rebuild_rankings(
    projects: Iterable[Project],
    *,
    tenant_id: Optional[int | str] = None,
) -> int:
    """Reconstrói rankings a partir do PostgreSQL e retorna projetos indexados."""
    client = _redis_client()
    if client is None:
        return 0
    keys = [ranking_key(period, tenant_id) for period in PERIODS]
    try:
        client.delete(*keys)
        count = 0
        for project in projects:
            if project.visibility != Project.VISIBILITY_PUBLIC:
                continue
            for period in PERIODS:
                _zadd(client, ranking_key(period, tenant_id), project.pk, _vote_count(project.pk, period))
            count += 1
        return count
    except Exception:
        logger.warning("Falha ao reconstruir ranking", extra={"tenant_id": tenant_id})
        return 0


def public_ranking_ids(period: str = "all", tenant_id: Optional[int | str] = None, limit: int = 20) -> list[int]:
    """Lê IDs da projeção; a consulta final deve revalidar visibilidade no SQL."""
    result = _safe(lambda client: client.zrevrange(ranking_key(period, tenant_id), 0, limit - 1))
    return [int(value) for value in (result or [])]
