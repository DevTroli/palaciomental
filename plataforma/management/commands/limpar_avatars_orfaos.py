"""Recupera mídia órfã após falha de upload, rollback ou interrupção do processo."""
from datetime import timedelta
from pathlib import PurePosixPath

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from plataforma.models import MemberProfile
from plataforma.profile_updates import remove_unused_avatar


class Command(BaseCommand):
    help = "Lista avatares sem referência há mais de 24 h; --aplicar remove os candidatos."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true")

    def handle(self, *args, **options):
        storage = MemberProfile._meta.get_field("avatar").storage
        cutoff = timezone.now() - timedelta(hours=24)
        candidates = removed = failures = 0
        try:
            _, files = storage.listdir("avatars")
        except FileNotFoundError:
            files = []
        for filename in files:
            # O fluxo de upload usa apenas arquivos diretos em avatars/.
            if PurePosixPath(filename).name != filename:
                continue
            name = f"avatars/{filename}"
            if MemberProfile.objects.filter(avatar=name).exists():
                continue
            try:
                modified = storage.get_modified_time(name)
                if timezone.is_naive(modified):
                    modified = timezone.make_aware(modified)
                if modified >= cutoff:
                    continue
            except FileNotFoundError:
                continue
            candidates += 1
            self.stdout.write(name)
            if options["aplicar"]:
                if remove_unused_avatar(storage, name):
                    removed += 1
                else:
                    failures += 1
        self.stdout.write(f"Candidatos: {candidates}; removidos: {removed}; falhas: {failures}.")
        if failures:
            raise CommandError("A limpeza não terminou. Consulte os registros e tente novamente.")
