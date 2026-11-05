from django.core.management.base import BaseCommand, CommandError

from core.rankings import rebuild_rankings
from plataforma.models import Project


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
            help="IDs opcionais de projetos públicos a reconstruir.",
        )

    def handle(self, *args, **options):
        tenant_id = options["tenant_id"]
        project_ids = options.get("project_ids")
        queryset = Project.objects.filter(visibility=Project.VISIBILITY_PUBLIC)
        if tenant_id is not None:
            queryset = queryset.filter(organizacao_id=tenant_id)
        if project_ids:
            queryset = queryset.filter(pk__in=project_ids)

        count = rebuild_rankings(queryset.iterator(), tenant_id=tenant_id)
        scope = "global" if tenant_id is None else f"tenant:{tenant_id}"
        self.stdout.write(self.style.SUCCESS(f"Ranking {scope} reconstruído com {count} projeto(s)."))
