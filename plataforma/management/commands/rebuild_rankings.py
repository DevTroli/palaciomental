from django.core.management.base import BaseCommand, CommandError

from core.rankings import rebuild_rankings
from plataforma.models import Project
from plataforma import rls
from django.conf import settings


class Command(BaseCommand):
    help = "Reconstrói rankings Redis a partir da fonte oficial PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            default=None,
            help="ID do tenant para uma projeção institucional isolada.",
        )
        parser.add_argument(
            "--project-ids",
            nargs="*",
            type=int,
            help="Filtro parcial não suportado; use uma reconstrução completa por escopo.",
        )

    def handle(self, *args, **options):
        tenant_id = options["tenant_id"]
        project_ids = options.get("project_ids")
        if project_ids is not None:
            raise CommandError("--project-ids não é suportado: reconstrua o escopo completo com --tenant-id ou sem filtro.")
        if not settings.REDIS_URL:
            raise CommandError("Configure REDIS_URL para reconstruir rankings.")
        queryset = Project.objects.filter(visibility=Project.VISIBILITY_PUBLIC, organizacao_id=tenant_id)
        if tenant_id is not None:
            queryset = queryset.filter(organizacao_id=tenant_id)

        try:
            mode = rls.MODE_TENANT if tenant_id is not None else rls.MODE_GLOBAL
            with rls.rls_context(mode, tenant_id):
                count = rebuild_rankings(queryset.iterator(), tenant_id=tenant_id)
        except Exception as exc:
            raise CommandError("Ranking não foi publicado; consulte o log da reconstrução.") from exc
        scope = "global" if tenant_id is None else f"tenant:{tenant_id}"
        self.stdout.write(self.style.SUCCESS(f"Ranking {scope} reconstruído com {count} projeto(s)."))
