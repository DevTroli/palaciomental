"""Integração opt-in; nunca limpa o banco Redis inteiro."""

import os
import uuid
from unittest import skipUnless

import redis
from django.core.management import call_command
from django.test import TestCase, override_settings

from django.contrib.auth import get_user_model
from core.rankings import ranked_projects, ranking_key, update_project_projection
from plataforma.models import Organizacao, Project, ProjectVote


@skipUnless(os.environ.get("TEST_REDIS_URL"), "Redis de teste não configurado")
class RedisRankingIntegrationTests(TestCase):
    def setUp(self):
        self.prefix = f"m6-test:{uuid.uuid4().hex}"
        self.url = os.environ["TEST_REDIS_URL"]
        self.config = override_settings(REDIS_URL=self.url, RANKING_KEY_PREFIX=self.prefix)
        self.config.enable()
        self.addCleanup(self.config.disable)
        self.client_redis = redis.Redis.from_url(self.url, decode_responses=True, socket_timeout=1)
        self.addCleanup(self.cleanup_keys)
        self.owner = get_user_model().objects.create_user(username="redis-integration")
        self.org = Organizacao.objects.create(nome="Redis A", slug="redis-a", status="ativa")
        self.personal = Project.objects.create(owner=self.owner, title="Pessoal", visibility="publico")
        self.institutional = Project.objects.create(owner=self.owner, organizacao=self.org, title="Institucional", visibility="publico")
        self.private = Project.objects.create(owner=self.owner, organizacao=self.org, title="Privado", visibility="privado")

    def cleanup_keys(self):
        keys = list(self.client_redis.scan_iter(match=f"{self.prefix}:*"))
        if keys:
            self.client_redis.delete(*keys)

    def test_rebuild_and_sql_revalidation_keep_tenants_separate(self):
        ProjectVote.objects.create(project=self.personal, user=self.owner)
        for project in (self.personal, self.institutional, self.private):
            update_project_projection(project.pk)
        self.client_redis.zadd(ranking_key("all"), {str(self.institutional.pk): 1000})
        self.client_redis.zadd(ranking_key("all", self.org.pk), {str(self.private.pk): 1000, str(self.personal.pk): 999})
        self.assertEqual(list(ranked_projects(Project.objects.all())), [self.personal])
        self.assertEqual(list(ranked_projects(Project.objects.all(), tenant_id=self.org.pk)), [self.institutional])
        call_command("rebuild_rankings", verbosity=0)
        self.assertEqual(self.client_redis.zrange(ranking_key("all"), 0, -1), [str(self.personal.pk)])
        call_command("rebuild_rankings", tenant_id=str(self.org.pk), verbosity=0)
        self.assertEqual(self.client_redis.zrange(ranking_key("all", self.org.pk), 0, -1), [str(self.institutional.pk)])
        self.assertEqual(list(self.client_redis.scan_iter(match=f"{self.prefix}:*:rebuild:*")), [])

    def test_deletion_after_outer_transaction_removes_institutional_projection(self):
        update_project_projection(self.institutional.pk)
        project_id = self.institutional.pk
        with self.captureOnCommitCallbacks(execute=True):
            self.institutional.delete()
        self.assertIsNone(self.client_redis.zscore(ranking_key("all", self.org.pk), str(project_id)))
