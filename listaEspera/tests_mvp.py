from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import MemberProfile, Project, ProjectMember

User = get_user_model()


class MvpAuthenticationTests(TestCase):
    def test_register_creates_user_profile_and_session(self):
        response = self.client.post(reverse("listaEspera:register"), {
            "first_name": "Pablo", "username": "pablo", "email": "pablo@example.com",
            "password1": "Senha-forte-123", "password2": "Senha-forte-123",
        })
        self.assertRedirects(response, reverse("listaEspera:profile", kwargs={"username": "pablo"}))
        user = User.objects.get(username="pablo")
        self.assertTrue(MemberProfile.objects.filter(user=user).exists())
        self.assertEqual(int(self.client.session.get("_auth_user_id")), user.pk)

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(username="one", email="same@example.com", password="Senha-forte-123")
        response = self.client.post(reverse("listaEspera:register"), {
            "first_name": "Dois", "username": "two", "email": "same@example.com",
            "password1": "Senha-forte-123", "password2": "Senha-forte-123",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "já está cadastrado")


class MvpProjectTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", email="owner@example.com", password="Senha-forte-123", first_name="Owner")
        self.collaborator = User.objects.create_user(username="collab", email="collab@example.com", password="Senha-forte-123")
        MemberProfile.objects.create(user=self.owner, bio="Crio coisas")
        self.project = Project.objects.create(owner=self.owner, title="Projeto Aurora", direction="Tornar ideias visíveis.", category="Educação", tags="pesquisa, educação")

    def test_public_project_appears_on_home_and_explorer(self):
        self.assertContains(self.client.get(reverse("listaEspera:index")), "Projeto Aurora")
        self.assertContains(self.client.get(reverse("listaEspera:projects")), "Projeto Aurora")
        self.assertContains(self.client.get(reverse("listaEspera:projects") + "?tag=pesquisa"), "Projeto Aurora")

    def test_owner_can_edit_and_anonymous_cannot_create(self):
        response = self.client.get(reverse("listaEspera:project_create"))
        self.assertRedirects(response, reverse("listaEspera:login") + "?next=/projetos/novo/")
        self.client.force_login(self.owner)
        response = self.client.post(reverse("listaEspera:project_edit", kwargs={"pk": self.project.pk}), {
            "title": "Projeto Aurora atualizado", "direction": "Direção atualizada", "status": "ativo",
            "visibility": "publico", "category": "Educação", "tags": "pesquisa",
        })
        self.assertRedirects(response, reverse("listaEspera:project_detail", kwargs={"pk": self.project.pk}))
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Projeto Aurora atualizado")

    def test_private_project_is_hidden_from_public_explorer(self):
        self.project.visibility = Project.VISIBILITY_PRIVATE
        self.project.save(update_fields=["visibility"])
        self.assertNotContains(self.client.get(reverse("listaEspera:projects")), "Projeto Aurora")
        self.client.force_login(self.collaborator)
        self.assertEqual(self.client.get(reverse("listaEspera:project_detail", kwargs={"pk": self.project.pk})).status_code, 404)
        ProjectMember.objects.create(project=self.project, user=self.collaborator)
        self.assertEqual(self.client.get(reverse("listaEspera:project_detail", kwargs={"pk": self.project.pk})).status_code, 200)
