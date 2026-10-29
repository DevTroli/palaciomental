from django.apps import AppConfig


class PlataformaConfig(AppConfig):
    name = "plataforma"
    # Mantém o app label legado para preservar tabelas e migrations já aplicadas.
    label = "listaEspera"
