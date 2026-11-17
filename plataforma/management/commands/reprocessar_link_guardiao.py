"""Libera um único item da fila para nova tentativa pelo worker."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from plataforma.models import GuardiaoLinkPendente
from plataforma.rls import system_context


class Command(BaseCommand):
    help = "Retira um ID da quarentena do Guardião, sem executar chamadas de rede."

    def add_arguments(self, parser):
        parser.add_argument("link_id", type=int)

    def handle(self, *args, **options):
        link_id = options["link_id"]
        if link_id <= 0:
            raise CommandError("Informe um ID positivo.")
        with transaction.atomic(), system_context():
            entry = GuardiaoLinkPendente.objects.select_for_update().filter(link_id=link_id).first()
            if entry is None:
                raise CommandError("ID não encontrado na fila do Guardião.")
            entry.quarentena = False
            entry.rejeicao_http = None
            entry.rejeitada_em = None
            entry.save(update_fields=["quarentena", "rejeicao_http", "rejeitada_em", "atualizado_em"])
        self.stdout.write(self.style.SUCCESS(f"Link {link_id} liberado para nova tentativa pelo worker."))
