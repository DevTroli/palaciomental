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
        if not user.is_active or not user.is_staff:
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=self.internal_groups).exists()
