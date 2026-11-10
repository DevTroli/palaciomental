from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from plataforma import rls


class Command(BaseCommand):
    help = "Mostra se a RLS está realmente efetiva para a role atual do banco."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="Falha se a RLS estiver inerte.")

    def handle(self, *args, strict=False, **options):
        if connection.vendor != "postgresql":
            raise CommandError("RLS exige PostgreSQL.")
        problemas = []
        with connection.cursor() as c:
            c.execute("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
            user, sup, byp = c.fetchone()
            self.stdout.write(f"role={user} superuser={sup} bypassrls={byp}")
            if sup or byp:
                problemas.append("role ignora RLS (superuser ou BYPASSRLS)")
            for t in rls.PROTECTED_TABLES:
                c.execute("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = %s::regclass", [t])
                on, force = c.fetchone()
                c.execute("SELECT polname FROM pg_policy WHERE polrelid = %s::regclass", [t])
                pols = [r[0] for r in c.fetchall()]
                self.stdout.write(f"{t}: enable={on} force={force} policies={pols}")
                if not (on and force and pols):
                    problemas.append(f"{t} sem RLS completa")
        for p in problemas:
            self.stdout.write(self.style.WARNING(p))
        if strict and problemas:
            raise CommandError("RLS inerte: " + "; ".join(problemas))
        if not problemas:
            self.stdout.write(self.style.SUCCESS("RLS efetiva."))
