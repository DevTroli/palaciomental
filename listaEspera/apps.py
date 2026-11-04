from django.apps import AppConfig


class ListaesperaConfig(AppConfig):
    name = "listaEspera"

    def ready(self):
        from . import ranking_signals  # noqa: F401
