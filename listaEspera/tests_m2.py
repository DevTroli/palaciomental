from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import CollaborationRequest, MemberProfile, Notification, Project, ProjectComment, ProjectMember, ProjectMilestone, ProjectVote

User = get_user_model()


class CommunityM2Tests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", email="owner@example.com", password="Senha-forte-123")
        self.member = User.objects.create_user(username="member", email="member@example.com", password="Senha-forte-123")
        MemberProfile.objects.create(user=self.owner)
        MemberProfile.objects.create(user=self.member)
        self.project = Project.objects.create(owner=self.owner, title="Projeto Aurora", direction="Direção", category="Educação", visibility=Project.VISIBILITY_PUBLIC, seeking_collaborators=True, collaboration_description="Pesquisa")

    def test_authenticated_member_can_comment_and_reply_only_one_level(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse("listaEspera:add_comment", args=[self.project.pk]), {"content": "Contexto importante"})
        self.assertEqual(response.status_code, 302)
        comment = ProjectComment.objects.get()
        self.client.post(reverse("listaEspera:add_comment", args=[self.project.pk]), {"content": "Resposta", "parent": comment.pk})
        reply = ProjectComment.objects.get(parent=comment)
        self.client.post(reverse("listaEspera:add_comment", args=[self.project.pk]), {"content": "Resposta inválida", "parent": reply.pk})
        self.assertEqual(ProjectComment.objects.count(), 2)

    def test_comment_owner_can_edit_and_delete(self):
        self.client.force_login(self.member)
        comment = ProjectComment.objects.create(project=self.project, author=self.member, content="Antes")
        self.client.post(reverse("listaEspera:edit_comment", args=[comment.pk]), {"content": "Depois"})
        comment.refresh_from_db()
        self.assertEqual(comment.content, "Depois")
        self.client.post(reverse("listaEspera:delete_comment", args=[comment.pk]))
        self.assertFalse(ProjectComment.objects.filter(pk=comment.pk).exists())

    def test_vote_toggles_and_is_unique(self):
        self.client.force_login(self.member)
        url = reverse("listaEspera:toggle_vote", args=[self.project.pk])
        self.client.post(url)
        self.assertEqual(ProjectVote.objects.count(), 1)
        self.client.post(url)
        self.assertEqual(ProjectVote.objects.count(), 0)

    def test_milestone_requires_owner_or_collaborator(self):
        self.client.force_login(self.member)
        url = reverse("listaEspera:add_milestone", args=[self.project.pk])
        self.assertEqual(self.client.post(url, {"title": "Não autorizado", "description": "x", "milestone_type": "avanco"}).status_code, 404)
        ProjectMember.objects.create(project=self.project, user=self.member)
        self.assertEqual(self.client.post(url, {"title": "Primeiro avanço", "description": "x", "milestone_type": "avanco"}).status_code, 302)
        self.assertTrue(ProjectMilestone.objects.filter(title="Primeiro avanço").exists())

    def test_collaboration_request_is_decided_and_notifies_requester(self):
        self.client.force_login(self.member)
        self.client.post(reverse("listaEspera:request_collaboration", args=[self.project.pk]), {"message": "Posso ajudar com pesquisa"})
        collaboration = CollaborationRequest.objects.get()
        self.assertEqual(collaboration.status, CollaborationRequest.PENDING)
        self.client.force_login(self.owner)
        self.client.post(reverse("listaEspera:decide_collaboration", args=[collaboration.pk]), {"decision": CollaborationRequest.ACCEPTED})
        self.assertFalse(CollaborationRequest.objects.filter(pk=collaboration.pk).exists())
        self.assertTrue(ProjectMember.objects.filter(project=self.project, user=self.member).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.member).exists())

    def test_private_project_blocks_public_comment_and_vote(self):
        self.project.visibility = Project.VISIBILITY_PRIVATE
        self.project.save(update_fields=["visibility"])
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(reverse("listaEspera:add_comment", args=[self.project.pk]), {"content": "x"}).status_code, 404)
        self.assertEqual(self.client.post(reverse("listaEspera:toggle_vote", args=[self.project.pk])).status_code, 404)


class M2AcceptanceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="author", password="Senha-forte-123")
        self.member = User.objects.create_user(username="reader", password="Senha-forte-123")
        MemberProfile.objects.create(user=self.owner)
        MemberProfile.objects.create(user=self.member)

    def test_restricted_project_requires_access_link_and_private_is_owner_only(self):
        restricted = Project.objects.create(owner=self.owner, title="Restrito", direction="Rumo", category="", visibility=Project.VISIBILITY_RESTRICTED)
        private = Project.objects.create(owner=self.owner, title="Privado", direction="Rumo", category="", visibility=Project.VISIBILITY_PRIVATE)
        self.assertEqual(self.client.get(reverse("listaEspera:project_detail", args=[restricted.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("listaEspera:project_detail", args=[restricted.pk]) + f"?access={restricted.access_token}").status_code, 200)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse("listaEspera:project_detail", args=[private.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("listaEspera:project_detail", args=[restricted.pk]) + f"?access={restricted.access_token}").status_code, 200)

    def test_create_starts_with_basics_then_generates_action_milestone(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("listaEspera:project_create"), {"title": "Nova ideia", "direction": "Um rumo", "status": "ideia", "visibility": "privado"})
        project = Project.objects.get(title="Nova ideia")
        self.assertRedirects(response, reverse("listaEspera:project_context", args=[project.pk]))
        self.assertTrue(ProjectMilestone.objects.filter(project=project, title="Projeto iniciado").exists())

    def test_context_can_add_links_and_creates_progress_milestone(self):
        project = Project.objects.create(owner=self.owner, title="Links", direction="Rumo", category="", visibility=Project.VISIBILITY_PRIVATE)
        self.client.force_login(self.owner)
        response = self.client.post(reverse("listaEspera:project_context", args=[project.pk]), {
            "category": "Pesquisa", "tags": "contexto, design", "visibility": "restrito", "seeking_collaborators": "",
            "collaboration_description": "", "links-TOTAL_FORMS": "1", "links-INITIAL_FORMS": "0", "links-MIN_NUM_FORMS": "0", "links-MAX_NUM_FORMS": "12",
            "links-0-label": "Documento", "links-0-url": "https://example.com",
        })
        project.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(project.visibility, Project.VISIBILITY_RESTRICTED)
        self.assertEqual(project.links.count(), 1)
        self.assertTrue(ProjectMilestone.objects.filter(project=project, description__icontains="links").exists())

    def test_unread_inbox_is_counted_and_marked_read_when_opened(self):
        notification = Notification.objects.create(recipient=self.owner, kind="test", message="Nova atualização")
        self.client.force_login(self.owner)
        response = self.client.get(reverse("listaEspera:inbox"))
        self.assertContains(response, "Nova atualização")
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)

    def test_member_without_milestone_permission_cannot_manage(self):
        project = Project.objects.create(owner=self.owner, title="Permissões", direction="Rumo", category="", visibility=Project.VISIBILITY_PUBLIC)
        ProjectMember.objects.create(project=project, user=self.member, can_manage_milestones=False)
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(reverse("listaEspera:add_milestone", args=[project.pk]), {"title": "x", "description": "x", "milestone_type": "avanco"}).status_code, 404)

class M2AuthorControlsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="titleowner", password="Senha-forte-123")
        self.other = User.objects.create_user(username="otherauthor", password="Senha-forte-123")
        MemberProfile.objects.create(user=self.owner)
        MemberProfile.objects.create(user=self.other)

    def test_owner_cannot_create_duplicate_project_title(self):
        Project.objects.create(owner=self.owner, title="Mesmo nome", direction="Rumo", category="", visibility=Project.VISIBILITY_PRIVATE)
        self.client.force_login(self.owner)
        response = self.client.post(reverse("listaEspera:project_create"), {"title": "mesmo nome", "direction": "Outro rumo", "status": "ideia", "visibility": "privado"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Você já possui um projeto com este título")
        self.assertEqual(Project.objects.filter(owner=self.owner).count(), 1)

    def test_only_original_author_can_delete_project(self):
        project = Project.objects.create(owner=self.owner, title="Excluir", direction="Rumo", category="", visibility=Project.VISIBILITY_PRIVATE)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("listaEspera:project_delete", args=[project.pk])).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse("listaEspera:project_delete", args=[project.pk])).status_code, 302)
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())
