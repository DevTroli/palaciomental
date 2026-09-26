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
        collaboration.refresh_from_db()
        self.assertEqual(collaboration.status, CollaborationRequest.ACCEPTED)
        self.assertTrue(ProjectMember.objects.filter(project=self.project, user=self.member).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.member).exists())

    def test_private_project_blocks_public_comment_and_vote(self):
        self.project.visibility = Project.VISIBILITY_PRIVATE
        self.project.save(update_fields=["visibility"])
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(reverse("listaEspera:add_comment", args=[self.project.pk]), {"content": "x"}).status_code, 404)
        self.assertEqual(self.client.post(reverse("listaEspera:toggle_vote", args=[self.project.pk])).status_code, 404)
