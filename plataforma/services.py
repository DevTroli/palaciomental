from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
import hashlib
import secrets
from datetime import timedelta

from .models import ConviteOrganizacao, MembroOrganizacao, Organizacao


PAPEIS_CONVIDAVEIS = {
    MembroOrganizacao.PAPEL_PROPRIETARIO: (MembroOrganizacao.PAPEL_GESTOR,),
    MembroOrganizacao.PAPEL_GESTOR: (MembroOrganizacao.PAPEL_PROFESSOR, MembroOrganizacao.PAPEL_MEMBRO),
    MembroOrganizacao.PAPEL_PROFESSOR: (MembroOrganizacao.PAPEL_MEMBRO,),
    MembroOrganizacao.PAPEL_MEMBRO: (),
}


def papeis_convidaveis(papel):
    return PAPEIS_CONVIDAVEIS.get(papel, ())


def emitir_convite_organizacao(organizacao, convidado_por, email, papel, dias_validade=7):
    permitidos = papeis_convidaveis(convidado_por.papel)
    if papel not in permitidos:
        raise ValidationError("Seu papel não pode convidar pessoas para este papel.")
    if organizacao.status != Organizacao.STATUS_ATIVA:
        raise ValidationError("O ambiente institucional ainda não está ativo.")
    if MembroOrganizacao.objects.filter(organizacao=organizacao, usuario__email__iexact=email).exists():
        raise ValidationError("Este e-mail já possui uma afiliação neste ambiente.")
    if ConviteOrganizacao.objects.filter(
        organizacao=organizacao,
        email__iexact=email,
        status=ConviteOrganizacao.STATUS_PENDENTE,
        expira_em__gt=timezone.now(),
    ).exists():
        raise ValidationError("Já existe um convite pendente para este e-mail.")
    raw_token = secrets.token_urlsafe(32)
    convite = ConviteOrganizacao.objects.create(
        organizacao=organizacao,
        convidado_por=convidado_por.usuario,
        email=email,
        papel=papel,
        hash_token=hashlib.sha256(raw_token.encode()).hexdigest(),
        expira_em=timezone.now() + timedelta(days=dias_validade),
    )
    return convite, raw_token


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
