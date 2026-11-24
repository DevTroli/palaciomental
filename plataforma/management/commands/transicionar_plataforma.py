from django.core.management.base import BaseCommand
from django.db import connections

from plataforma.legacy_transition import transition


class Command(BaseCommand):
    help = "Confere a transição do app histórico para plataforma; grava somente com --aplicar."

    def add_arguments(self, parser):
        parser.add_argument("--database", default="default")
        parser.add_argument("--aplicar", action="store_true")

    def handle(self, *args, **options):
        count = transition(connections[options["database"]], apply=options["aplicar"])
        action = "renomeados" if options["aplicar"] else "previstos (nenhuma alteração)"
        self.stdout.write(f"Objetos: {count} {action}.")
