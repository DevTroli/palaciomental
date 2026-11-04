from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from listaEspera.models import Project, ProjectVote

from .rankings import (
    public_ranking_ids,
    ranking_key,
    rebuild_rankings,
    remove_project_from_rankings,
    update_project_projection,
)

User = get_user_model()


class FakeRedis:
    def __init__(self):
        self.data = {}

    def zadd(self, key, values):
        self.data.setdefault(key, {}).update(values)

    def zrem(self, key, member):
        self.data.setdefault(key, {}).pop(str(member), None)

    def zincrby(self, key, amount, member):
        values = self.data.setdefault(key, {})
        values[str(member)] = values.get(str(member), 0) + amount

    def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)

    def zrevrange(self, key, start, stop):
        members = sorted(self.data.get(key, {}).items(), key=lambda item: (-item[1], int(item[0])))
        return [member for member, _score in members[start : stop + 1]]


@override_settings(REDIS_URL="redis://fake/1")
class RankingProjectionTests(TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.owner = User.objects.create_user(username="rank-owner", password="secret")
        self.other = User.objects.create_user(username="rank-other", password="secret")
        self.public = Project.objects.create(
            owner=self.owner,
            title="Projeto público",
            direction="Direção",
            category="Pesquisa",
            visibility=Project.VISIBILITY_PUBLIC,
        )
        self.private = Project.objects.create(
            owner=self.owner,
            title="Projeto privado",
            direction="Direção",
            category="Pesquisa",
            visibility=Project.VISIBILITY_PRIVATE,
        )

    def test_vote_projection_is_idempotent_and_private_never_enters_public_ranking(self):
        with patch("core.rankings.redis.Redis.from_url", return_value=self.redis):
            ProjectVote.objects.create(project=self.public, user=self.other)
            update_project_projection(self.public.pk)
            update_project_projection(self.public.pk)
            update_project_projection(self.private.pk)

            key = ranking_key("all")
            self.assertEqual(self.redis.data[key][str(self.public.pk)], 1)
            self.assertNotIn(str(self.private.pk), self.redis.data[key])

    def test_global_and_institutional_sets_are_separate(self):
        with patch("core.rankings.redis.Redis.from_url", return_value=self.redis):
            update_project_projection(self.public.pk, tenant_id="org-a")

            self.assertIn(str(self.public.pk), self.redis.data[ranking_key("all")])
            self.assertIn(str(self.public.pk), self.redis.data[ranking_key("all", "org-a")])
            self.assertNotIn(ranking_key("all", "org-b"), self.redis.data)

    def test_confirmed_vote_uses_increment_without_duplicate_score(self):
        from core.rankings import adjust_project_projection

        with patch("core.rankings.redis.Redis.from_url", return_value=self.redis):
            adjust_project_projection(self.public.pk, 1)
            adjust_project_projection(self.public.pk, -1)

            self.assertEqual(self.redis.data[ranking_key("all")][str(self.public.pk)], 0)

    def test_rebuild_reads_postgresql_and_removes_stale_members(self):
        with patch("core.rankings.redis.Redis.from_url", return_value=self.redis):
            self.redis.zadd(ranking_key("all"), {"999": 10})
            count = rebuild_rankings(Project.objects.all())

            self.assertEqual(count, 1)
            self.assertNotIn("999", self.redis.data[ranking_key("all")])
            self.assertIn(str(self.public.pk), self.redis.data[ranking_key("all")])

    def test_remove_project_erases_all_periods(self):
        with patch("core.rankings.redis.Redis.from_url", return_value=self.redis):
            update_project_projection(self.public.pk)
            remove_project_from_rankings(self.public.pk)

            for period in ("all", "weekly", "monthly"):
                self.assertNotIn(str(self.public.pk), self.redis.data.get(ranking_key(period), {}))

    def test_read_returns_ids_from_projection(self):
        with patch("core.rankings.redis.Redis.from_url", return_value=self.redis):
            update_project_projection(self.public.pk)
            self.assertEqual(public_ranking_ids(), [self.public.pk])
