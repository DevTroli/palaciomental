from django.core.management.commands.migrate import Command as MigrateCommand
from django.db import connections


class Command(MigrateCommand):
    help = "Serializa migrations de réplicas web que usam o mesmo PostgreSQL."

    def handle(self, *args, **options):
        db = connections[options["database"]]
        if db.vendor != "postgresql":
            return super().handle(*args, **options)
        # Chave estável entre releases. PostgreSQL libera o lock se o processo cair.
        lock_id = 0x504D4D494752
        with db.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [lock_id])
            try:
                return super().handle(*args, **options)
            finally:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
