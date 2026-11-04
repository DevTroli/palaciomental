"""Eventos transitórios de comentários; PostgreSQL permanece como origem oficial."""

import json
import logging

import redis
from django.conf import settings

logger = logging.getLogger(__name__)


def comment_channel(project_id: int, tenant_id=None) -> str:
    scope = f"tenant:{tenant_id}" if tenant_id is not None else "project"
    return f"comments:{scope}:{project_id}"


def publish_comment_event(event: str, comment_id: int, project_id: int, tenant_id=None) -> bool:
    """Publica após commit; falha no Redis nunca desfaz o comentário SQL."""
    url = getattr(settings, "REDIS_URL", "")
    if not url:
        return False
    payload = json.dumps({"event": event, "comment_id": comment_id, "project_id": project_id})
    try:
        client = redis.Redis.from_url(url, decode_responses=True)
        client.publish(comment_channel(project_id, tenant_id), payload)
        return True
    except Exception:
        logger.warning("Falha ao publicar evento transitório de comentário", extra={"project_id": project_id})
        return False
