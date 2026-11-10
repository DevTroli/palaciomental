from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

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
