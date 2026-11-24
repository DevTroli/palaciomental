from django.apps import AppConfig


class PlataformaConfig(AppConfig):
    name = "plataforma"
    verbose_name = "Operação da Plataforma"

    def ready(self):
        # Registra o sinal que aplica o escopo padrão de RLS em conexões novas.
        from . import rls  # noqa: F401
        from . import ranking_signals  # noqa: F401
        from . import guardiao_signals  # noqa: F401
