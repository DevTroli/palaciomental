from django.conf import settings
from django.http import HttpResponseForbidden


class InternalAdminAccessMiddleware:
    """Mantém o Django Admin restrito à equipe operacional do Palácio Mental."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.internal_groups = set(getattr(settings, "PM_INTERNAL_ADMIN_GROUPS", ("Equipe PM",)))

    def __call__(self, request):
        if not request.path.startswith("/admin/"):
            return self.get_response(request)

        # A tela de autenticação precisa estar disponível para a equipe iniciar sessão.
        # A autorização real acontece assim que o usuário autenticado acessa o admin.
        if not request.user.is_authenticated:
            return self.get_response(request)

        if self._is_internal_admin(request.user):
            return self.get_response(request)

        return HttpResponseForbidden(
            "Esta área é exclusiva da equipe interna do Palácio Mental. "
            "Use o ambiente institucional da sua organização."
        )

    def _is_internal_admin(self, user):
        return is_internal_admin(user, self.internal_groups)


def is_internal_admin(user, internal_groups=None):
    """Equipe operacional do PM: staff ativo, superusuário ou grupo interno."""
    if not user.is_active or not user.is_staff:
        return False
    if user.is_superuser:
        return True
    groups = internal_groups if internal_groups is not None else set(getattr(settings, "PM_INTERNAL_ADMIN_GROUPS", ("Equipe PM",)))
    return user.groups.filter(name__in=groups).exists()
