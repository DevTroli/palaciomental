from functools import wraps

from django.http import Http404


def tenant_required(view):
    """Funcionalidade institucional exige tenant e afiliação ativa resolvidos."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not getattr(request, "organizacao", None):
            raise Http404
        # O middleware autentica e valida a afiliação antes de alcançar a view.
        if not getattr(request, "membro_organizacao", None):
            raise Http404
        return view(request, *args, **kwargs)
    return wrapped
