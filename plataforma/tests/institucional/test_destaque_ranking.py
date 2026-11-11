from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from unittest.mock import patch

from plataforma.models import MembroOrganizacao, Project, ProjectVote
from .base import PortalInstitucionalBase

HOST = "camppg.palaciomental.com.br"


@override_settings(REDIS_URL="")
class DestaqueRankingTests(PortalInstitucionalBase):
    def setUp(self):
        super().setUp()
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user)
        self.client.force_login(self.user)

    def test_badge_appears_only_for_five_recognized_public_projects(self):
        voters = [get_user_model().objects.create_user(username=f"voto{i}") for i in range(6)]
        projects = []
        for i in range(6):
            project = Project.objects.create(owner=self.user, organizacao=self.organization, title=f"Projeto {i}", visibility=Project.VISIBILITY_PUBLIC)
            projects.append(project)
            for voter in voters[:6-i]:
                ProjectVote.objects.create(project=project, user=voter)
        for index, project in enumerate(projects):
            response = self.client.get(reverse("plataforma:project_detail", args=[project.pk]), HTTP_HOST=HOST)
            if index < 5:
                self.assertContains(response, "Destaque da comunidade")
            else:
                self.assertNotContains(response, "Destaque da comunidade")
        unrecognized = Project.objects.create(owner=self.user, organizacao=self.organization, title="Sem votos", visibility=Project.VISIBILITY_PUBLIC)
        self.assertNotContains(self.client.get(reverse("plataforma:project_detail", args=[unrecognized.pk]), HTTP_HOST=HOST), "Destaque da comunidade")
        home = self.client.get("/", HTTP_HOST=HOST)
        ranking = list(home.context["ranking_projetos"])
        self.assertEqual([project.pk for project in ranking], [project.pk for project in projects[:5]])
        self.assertNotContains(home, "Explorar por relevância")

    def test_guidance_is_available_inside_tenant(self):
        response = self.client.get(reverse("plataforma:guidance"), HTTP_HOST=HOST)
        self.assertContains(response, "Orientações e avisos")
        self.assertContains(response, "A área de avisos está em desenvolvimento.")
        self.assertContains(self.client.get("/", HTTP_HOST=HOST), reverse("plataforma:guidance"))

    def test_home_and_project_badges_follow_redis_ranking(self):
        from core.rankings import update_project_projection
        from core.test_rankings import FakeRedis

        voters = [get_user_model().objects.create_user(username=f"redis-home-voto{i}") for i in range(5)]
        projects = []
        for i in range(5):
            project = Project.objects.create(owner=self.user, organizacao=self.organization, title=f"Ranking {i}", visibility=Project.VISIBILITY_PUBLIC)
            projects.append(project)
            for voter in voters[:i + 1]:
                ProjectVote.objects.create(project=project, user=voter)
        cache = FakeRedis()
        with patch("core.rankings._redis_client", return_value=cache):
            for project in projects:
                update_project_projection(project.pk)
            home = self.client.get("/", HTTP_HOST=HOST)
            self.assertEqual([project.pk for project in home.context["ranking_projetos"]], [project.pk for project in reversed(projects)])
            for position, project in enumerate(reversed(projects), 1):
                detail = self.client.get(reverse("plataforma:project_detail", args=[project.pk]), HTTP_HOST=HOST)
                self.assertEqual(detail.context["ranking_posicao"], position)
