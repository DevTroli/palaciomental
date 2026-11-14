from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.test import TestCase, override_settings

from plataforma.models import Project, ProjectVote, Organizacao

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

    def expire(self, key, timeout):
        return True

    def persist(self, key):
        return True

    def rename(self, source, target):
        self.data[target] = self.data.pop(source)

    def pipeline(self, transaction=True):
        return self

    def execute(self):
        return []

    def zrevrange(self, key, start, stop, withscores=False):
        members = sorted(self.data.get(key, {}).items(), key=lambda item: (-item[1], int(item[0])))
        selected = members[start : stop + 1 if stop >= 0 else None]
        return selected if withscores else [member for member, _score in selected]

    def zrange(self, key, start, stop, withscores=False):
        members = sorted(self.data.get(key, {}).items(), key=lambda item: (item[1], int(item[0])))
        selected = members[start : stop + 1 if stop >= 0 else None]
        return selected if withscores else [member for member, _score in selected]


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
        org = Organizacao.objects.create(nome="Organização A", slug="org-a", status="ativa")
        institutional = Project.objects.create(owner=self.owner, organizacao=org,
                                               title="Projeto institucional", visibility="publico")
        with patch("core.rankings.redis.Redis.from_url", return_value=self.redis):
            update_project_projection(self.public.pk)
            update_project_projection(institutional.pk)
            self.assertIn(str(self.public.pk), self.redis.data[ranking_key("all")])
            self.assertNotIn(str(institutional.pk), self.redis.data[ranking_key("all")])
            self.assertIn(str(institutional.pk), self.redis.data[ranking_key("all", org.pk)])
            self.assertNotIn(str(self.public.pk), self.redis.data[ranking_key("all", org.pk)])

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

    def test_partial_projection_falls_back_to_sql_ordering(self):
        from core.rankings import ranked_projects

        older = Project.objects.create(
            owner=self.owner,
            title="Projeto com relevância SQL",
            direction="Direção",
            category="Pesquisa",
            visibility=Project.VISIBILITY_PUBLIC,
        )
        for index in range(3):
            ProjectVote.objects.create(
                project=older,
                user=User.objects.create_user(username=f"voter-{index}"),
            )
        with patch("core.rankings.redis.Redis.from_url", return_value=self.redis):
            self.redis.zadd(ranking_key("all"), {str(self.public.pk): 1})
            queryset = Project.objects.filter(
                pk__in=[self.public.pk, older.pk]
            ).annotate(relevance=Count("votes", distinct=True))
            result = list(ranked_projects(queryset, tenant_id=None))
        self.assertEqual([project.pk for project in result], [older.pk, self.public.pk])

    def test_complete_projection_orders_highest_first_and_matches_sql_on_ties(self):
        from core.rankings import ranked_projects

        mais_votado = Project.objects.create(owner=self.owner, title="Mais reconhecido", visibility=Project.VISIBILITY_PUBLIC)
        empatado = Project.objects.create(owner=self.owner, title="Mesmo número de votos", visibility=Project.VISIBILITY_PUBLIC)
        for index in range(2):
            voter = User.objects.create_user(username=f"rank-voter-{index}")
            ProjectVote.objects.create(project=mais_votado, user=voter)
            ProjectVote.objects.create(project=empatado, user=voter)
        ProjectVote.objects.create(project=self.public, user=self.other)
        queryset = Project.objects.filter(pk__in=[self.public.pk, mais_votado.pk, empatado.pk])
        with patch("core.rankings.redis.Redis.from_url", return_value=self.redis):
            for project in (self.public, mais_votado, empatado):
                update_project_projection(project.pk)
            redis_order = list(ranked_projects(queryset).values_list("pk", flat=True))
        with override_settings(REDIS_URL=""):
            sql_order = list(ranked_projects(queryset).values_list("pk", flat=True))
        self.assertEqual(redis_order, sql_order)
        self.assertEqual(redis_order, [empatado.pk, mais_votado.pk, self.public.pk])
