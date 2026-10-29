from django.core.exceptions import ValidationError
from django.db import transaction

from .models import MembroOrganizacao, Organizacao


def ativar_organizacao(organizacao, executor=None):
    """Ativa um tenant somente quando identidade, domínio e proprietário estão prontos."""
    if organizacao.status == Organizacao.STATUS_ATIVA:
        return organizacao
    if organizacao.status != Organizacao.STATUS_CONFIGURANDO:
        raise ValidationError("Somente uma organização em configuração pode ser ativada.")
    if executor is None or not executor.is_staff:
        raise ValidationError("Somente a equipe do Palácio Mental pode ativar a organização.")
    identidade = getattr(organizacao, "identidade", None)
    if identidade is None or not identidade.completa:
        raise ValidationError("Configure a logo e as três cores institucionais antes de ativar.")
    if not organizacao.dominios.filter(principal=True, status_verificacao="ativo").exists():
        raise ValidationError("Cadastre e verifique o domínio principal antes de ativar.")
    if not organizacao.afiliacoes.filter(
        papel=MembroOrganizacao.PAPEL_PROPRIETARIO,
        status=MembroOrganizacao.STATUS_ATIVA,
    ).exists():
        raise ValidationError("A organização precisa ter um proprietário ativo.")
    with transaction.atomic():
        organizacao.status = Organizacao.STATUS_ATIVA
        organizacao.save(update_fields=["status", "atualizado_em"])
    return organizacao
