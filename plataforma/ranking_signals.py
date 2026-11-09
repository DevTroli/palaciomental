from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Project, ProjectComment, ProjectVote


def _refresh(project_id):
    from core.rankings import update_project_projection

    update_project_projection(project_id)


@receiver(post_save, sender=Project)
def project_saved_for_ranking(sender, instance, **kwargs):
    transaction.on_commit(lambda project_id=instance.pk: _refresh(project_id))


@receiver(post_delete, sender=Project)
def project_deleted_from_ranking(sender, instance, **kwargs):
    from core.rankings import remove_project_from_rankings

    transaction.on_commit(lambda project_id=instance.pk, tenant_id=instance.organizacao_id: remove_project_from_rankings(project_id, tenant_id=tenant_id))


@receiver(post_save, sender=ProjectVote)
def vote_saved_for_ranking(sender, instance, created, **kwargs):
    if not created:
        return
    from core.rankings import adjust_project_projection

    transaction.on_commit(
        lambda project_id=instance.project_id, created_at=instance.created_at: adjust_project_projection(
            project_id, 1, occurred_at=created_at
        )
    )


@receiver(post_delete, sender=ProjectVote)
def vote_deleted_from_ranking(sender, instance, **kwargs):
    from core.rankings import adjust_project_projection

    transaction.on_commit(
        lambda project_id=instance.project_id, created_at=instance.created_at: adjust_project_projection(
            project_id, -1, occurred_at=created_at
        )
    )


def _publish_comment(event, comment_id, project_id):
    from core.comment_events import publish_comment_event

    publish_comment_event(event, comment_id, project_id)


@receiver(post_save, sender=ProjectComment)
def comment_saved_event(sender, instance, created, **kwargs):
    event = "comment.created" if created else "comment.updated"
    transaction.on_commit(lambda comment_id=instance.pk, project_id=instance.project_id: _publish_comment(event, comment_id, project_id))


@receiver(post_delete, sender=ProjectComment)
def comment_deleted_event(sender, instance, **kwargs):
    transaction.on_commit(lambda comment_id=instance.pk, project_id=instance.project_id: _publish_comment("comment.deleted", comment_id, project_id))
