"""Registra alterações dos links na mesma transação do projeto."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import GuardiaoLinkPendente, ProjectLink


@receiver(post_save, sender=ProjectLink)
@receiver(post_delete, sender=ProjectLink)
def enfileirar_link(sender, instance, using, **kwargs):
    GuardiaoLinkPendente.objects.using(using).update_or_create(link_id=instance.pk)
