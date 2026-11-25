from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from plataforma.models import MemberProfile, Project, ProjectMember

User = get_user_model()


class MvpAuthenticationTests(TestCase):
    def test_register_creates_user_profile_and_session(self):
        response = self.client.post(reverse("plataforma:register"), {
            "first_name": "Pablo", "username": "pablo", "email": "pablo@example.com",
            "password1": "Senha-forte-123", "password2": "Senha-forte-123",
        })
        self.assertRedirects(response, reverse("plataforma:profile", kwargs={"username": "pablo"}))
        user = User.objects.get(username="pablo")
        self.assertTrue(MemberProfile.objects.filter(user=user).exists())
        session_user_id = self.client.session.get("_auth_user_id")
        assert session_user_id is not None
        self.assertEqual(int(session_user_id), user.pk)

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(username="one", email="same@example.com", password="Senha-forte-123")
        response = self.client.post(reverse("plataforma:register"), {
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
        self.project = Project.objects.create(owner=self.owner, title="Projeto Aurora", direction="Tornar ideias visíveis.", category="Educação", tags="pesquisa, educação", visibility=Project.VISIBILITY_PUBLIC)

    def test_public_project_appears_on_home_and_explorer(self):
        self.assertContains(self.client.get(reverse("core:index")), "Projeto Aurora")
        self.assertContains(self.client.get(reverse("plataforma:projects")), "Projeto Aurora")
        self.assertContains(self.client.get(reverse("plataforma:projects") + "?tag=pesquisa"), "Projeto Aurora")

    def test_owner_can_edit_and_anonymous_cannot_create(self):
        response = self.client.get(reverse("plataforma:project_create"))
        self.assertRedirects(response, reverse("plataforma:login") + "?next=/projetos/novo/")
        self.client.force_login(self.owner)
        response = self.client.post(reverse("plataforma:project_edit", kwargs={"pk": self.project.pk}), {
            "title": "Projeto Aurora atualizado", "direction": "Direção atualizada", "status": "ativo",
            "visibility": "publico", "category": "Educação", "tags": "pesquisa",
        })
        self.assertRedirects(response, reverse("plataforma:project_detail", kwargs={"pk": self.project.pk}))
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Projeto Aurora atualizado")

    def test_private_project_is_hidden_from_public_explorer(self):
        self.project.visibility = Project.VISIBILITY_PRIVATE
        self.project.save(update_fields=["visibility"])
        self.assertNotContains(self.client.get(reverse("plataforma:projects")), "Projeto Aurora")
        self.client.force_login(self.collaborator)
        self.assertEqual(self.client.get(reverse("plataforma:project_detail", kwargs={"pk": self.project.pk})).status_code, 404)
        ProjectMember.objects.create(project=self.project, user=self.collaborator)
        self.assertEqual(self.client.get(reverse("plataforma:project_detail", kwargs={"pk": self.project.pk})).status_code, 404)

    def test_skip_context_does_not_erase_existing_values(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("plataforma:project_context", args=[self.project.pk]), {"skip": "1"})
        self.assertRedirects(response, reverse("plataforma:project_detail", args=[self.project.pk]))
        self.project.refresh_from_db()
        self.assertEqual(self.project.category, "Educação")
        self.assertEqual(self.project.tags, "pesquisa, educação")

    def test_context_save_preserves_legacy_tags(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("plataforma:project_context", args=[self.project.pk]), {
            "category": "Pesquisa", "visibility": "publico",
            "links-TOTAL_FORMS": "0", "links-INITIAL_FORMS": "0",
        })
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.category, "Pesquisa")
        self.assertEqual(self.project.tags, "pesquisa, educação")

    def test_owner_edits_direction_in_place_without_changing_other_fields(self):
        url = reverse("plataforma:project_edit", args=[self.project.pk])
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("plataforma:project_detail", args=[self.project.pk])),
                            "Editar ponto de partida")
        response = self.client.post(url, {"edit_section": "direction", "direction": "Novo propósito"})
        self.assertRedirects(response, reverse("plataforma:project_detail", args=[self.project.pk]))
        self.project.refresh_from_db()
        self.assertEqual(self.project.direction, "Novo propósito")
        self.assertEqual(self.project.title, "Projeto Aurora")
        self.assertEqual(self.project.tags, "pesquisa, educação")
        response = self.client.post(url, {"edit_section": "direction", "direction": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este campo é obrigatório")
        self.project.refresh_from_db()
        self.assertEqual(self.project.direction, "Novo propósito")
        self.client.force_login(self.collaborator)
        self.assertNotContains(self.client.get(reverse("plataforma:project_detail", args=[self.project.pk])),
                               "Editar ponto de partida")
        self.assertEqual(self.client.post(url, {"edit_section": "direction", "direction": "Inválido"}).status_code, 404)
