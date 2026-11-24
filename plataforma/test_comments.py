from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.comment_events import publish_comment_event
from .models import Project, ProjectComment

User = get_user_model()


class NestedCommentTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="comment-author", password="secret")
        self.other = User.objects.create_user(username="comment-other", password="secret")
        self.project = Project.objects.create(
            owner=self.author,
            title="Projeto de comentários",
            direction="Contexto",
            category="Pesquisa",
            visibility=Project.VISIBILITY_PUBLIC,
        )
        self.other_project = Project.objects.create(
            owner=self.author,
            title="Outro projeto",
            direction="Contexto",
            category="Pesquisa",
            visibility=Project.VISIBILITY_PUBLIC,
        )

    def test_parent_must_belong_to_same_project(self):
        parent = ProjectComment.objects.create(project=self.project, author=self.author, content="Pai")
        child = ProjectComment(project=self.other_project, author=self.other, parent=parent, content="Filho")

        with self.assertRaises(ValidationError):
            child.full_clean()


    def test_comment_is_persisted_when_redis_event_publication_fails(self):
        with patch("core.comment_events.redis.Redis.from_url", side_effect=ConnectionError):
            comment = ProjectComment.objects.create(project=self.project, author=self.author, content="Persistente")
            self.assertTrue(ProjectComment.objects.filter(pk=comment.pk).exists())
            self.assertFalse(publish_comment_event("comment.created", comment.pk, self.project.pk))
