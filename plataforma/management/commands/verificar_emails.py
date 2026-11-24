from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.db.models.functions import Lower, Trim


class Command(BaseCommand):
    help = "Inventaria duplicatas de e-mail sem alterar contas ou exibir endereços."

    def handle(self, *args, **options):
        users = get_user_model().objects.annotate(normalized=Lower(Trim("email")))
        duplicates = list(users.exclude(normalized="").order_by().values("normalized")
                          .annotate(total=Count("pk")).filter(total__gt=1))
        self.stdout.write(f"Contas sem e-mail: {users.filter(normalized='').count()}")
        for group in duplicates:
            ids = list(users.filter(normalized=group["normalized"]).order_by("pk").values_list("pk", flat=True))
            self.stdout.write(f"Grupo duplicado: IDs {ids}")
        if duplicates:
            raise CommandError(f"{len(duplicates)} grupos duplicados exigem resolução aprovada.")
        self.stdout.write("Nenhum e-mail duplicado.")
