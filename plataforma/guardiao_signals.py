"""Registra alterações dos links na mesma transação do projeto."""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import GuardiaoLinkPendente, ProjectLink


@receiver(pre_save, sender=ProjectLink)
def detectar_alteracao_url(sender, instance, using, update_fields=None, **kwargs):
    instance._guardiao_reativar = False
    if not instance.pk or (update_fields is not None and "url" not in update_fields):
        return
    anterior = sender.objects.using(using).filter(pk=instance.pk).values_list("url", flat=True).first()
    instance._guardiao_reativar = anterior is not None and anterior != instance.url


@receiver(post_save, sender=ProjectLink)
@receiver(post_delete, sender=ProjectLink)
def enfileirar_link(sender, instance, using, signal, created=False, **kwargs):
    reativar = signal is post_delete or created or getattr(instance, "_guardiao_reativar", False)
    defaults = {"quarentena": False, "rejeicao_http": None, "rejeitada_em": None} if reativar else {}
    GuardiaoLinkPendente.objects.using(using).update_or_create(link_id=instance.pk, defaults=defaults)
