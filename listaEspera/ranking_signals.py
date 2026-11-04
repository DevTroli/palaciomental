from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Project, ProjectVote


def _refresh(project_id):
    from core.rankings import update_project_projection

    update_project_projection(project_id)


@receiver(post_save, sender=Project)
def project_saved_for_ranking(sender, instance, **kwargs):
    transaction.on_commit(lambda: _refresh(instance.pk))


@receiver(post_delete, sender=Project)
def project_deleted_from_ranking(sender, instance, **kwargs):
    from core.rankings import remove_project_from_rankings

    transaction.on_commit(lambda: remove_project_from_rankings(instance.pk))


@receiver(post_save, sender=ProjectVote)
def vote_saved_for_ranking(sender, instance, **kwargs):
    from core.rankings import adjust_project_projection

    transaction.on_commit(
        lambda: adjust_project_projection(
            instance.project_id, 1, occurred_at=instance.created_at
        )
    )


@receiver(post_delete, sender=ProjectVote)
def vote_deleted_from_ranking(sender, instance, **kwargs):
    from core.rankings import adjust_project_projection

    transaction.on_commit(
        lambda: adjust_project_projection(
            instance.project_id, -1, occurred_at=instance.created_at
        )
    )
