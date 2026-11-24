from django.core.management.base import CommandError
from django.core.management.commands.migrate import Command as DjangoMigrateCommand
from django.db import connections

from plataforma.legacy_transition import has_legacy_history


class Command(DjangoMigrateCommand):
    def handle(self, *args, **options):
        if has_legacy_history(connections[options["database"]]):
            raise CommandError(
                "Banco com identificador antigo. Faça backup, pare web e worker e execute "
                "transicionar_plataforma --aplicar antes de migrate. Consulte docs/transicao-plataforma.md."
            )
        return super().handle(*args, **options)
