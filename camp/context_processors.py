from django.conf import settings


def demo_access(request):
    """Expõe nos templates se o acesso de demonstração ao CAMP está habilitado."""
    return {"camp_demo_enabled": bool(settings.DEBUG)}
