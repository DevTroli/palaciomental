"""Readiness pública sem dados de negócio ou detalhes da conexão."""
import logging

from django.db import DatabaseError, connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)
HEALTH_PATHS = {"/saude", "/pronto"}


@require_safe
def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            return JsonResponse({"status": "not_ready"}, status=503)
    except DatabaseError:
        logger.warning("Readiness: banco indisponível.")
        return JsonResponse({"status": "not_ready"}, status=503)
    except Exception:
        logger.exception("Readiness: não foi possível validar o schema.")
        return JsonResponse({"status": "not_ready"}, status=503)
    return JsonResponse({"status": "ok"})
