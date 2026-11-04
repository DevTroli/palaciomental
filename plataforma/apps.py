from django.apps import AppConfig


class PlataformaConfig(AppConfig):
    name = "plataforma"
    verbose_name = "Operação da Plataforma"
    # Mantém o app label legado para preservar tabelas e migrations já aplicadas.
    label = "listaEspera"

    def ready(self):
        # Registra o sinal que aplica o escopo padrão de RLS em conexões novas.
        from . import rls  # noqa: F401
