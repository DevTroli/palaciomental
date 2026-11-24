from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from plataforma.models import MemberProfile, Project, ProjectLink


class AmeacasFormularioTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="autor_ameacas")
        MemberProfile.objects.create(user=self.user)
        self.project = Project.objects.create(owner=self.user, title="Projeto", direction="Rumo")
        self.client.force_login(self.user)
        self.url = reverse("plataforma:project_context", args=[self.project.pk])
        self.data = {
            "category": "Pesquisa", "tags": "", "visibility": "privado",
            "collaboration_description": "", "links-TOTAL_FORMS": "1", "links-INITIAL_FORMS": "0",
            "links-0-label": "Documento", "links-0-url": "https://example.com/",
        }

    @patch("plataforma.guardiao_consulta.consultar_ameacas", return_value=["THREAT"])
    def test_ameaca_confirmada_impede_salvar(self, consulta):
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este link pode representar uma ameaça")
        self.assertFalse(ProjectLink.objects.filter(project=self.project).exists())
        consulta.assert_called_once_with(["https://example.com/"])

    def test_prototipo_desativado_salva_com_aviso(self):
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ProjectLink.objects.filter(project=self.project).exists())
        self.assertTrue(any("verificação de ameaças não está disponível" in str(message)
                            for message in get_messages(response.wsgi_request)))

    @patch("plataforma.guardiao_consulta.consultar_ameacas", return_value=["NO_MATCH"])
    def test_sem_correspondencia_salva_sem_aviso(self, consulta):
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ProjectLink.objects.filter(project=self.project).exists())
        self.assertFalse(any("verificação de ameaças" in str(message)
                             for message in get_messages(response.wsgi_request)))


class AmeacasLinksSalvosTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="autor_reavaliacao")
        MemberProfile.objects.create(user=self.user)
        self.project = Project.objects.create(owner=self.user, title="Projeto", direction="Rumo")
        self.link = ProjectLink.objects.create(project=self.project, label="Referência", url="https://example.com/")

    @patch("plataforma.guardiao_ameacas.consultar_ameacas_detalhes")
    def test_ameaca_e_notificada_uma_vez_e_reclassificada(self, consulta):
        from datetime import timedelta
        from django.utils import timezone
        from plataforma.guardiao_ameacas import verificar_links_salvos
        from plataforma.models import Notification

        now = timezone.now()
        consulta.return_value = [{"state": "THREAT", "checked_at": now, "expires_at": now + timedelta(minutes=10)}]
        verificar_links_salvos()
        self.link.refresh_from_db()
        self.assertEqual(self.link.ameaca_estado, "THREAT")
        self.assertEqual(Notification.objects.filter(recipient=self.user, kind="guardiao_ameaca").count(), 1)
        ProjectLink.objects.filter(pk=self.link.pk).update(ameaca_proxima_verificacao=now)
        verificar_links_salvos()
        self.assertEqual(Notification.objects.filter(recipient=self.user, kind="guardiao_ameaca").count(), 1)
        ProjectLink.objects.filter(pk=self.link.pk).update(ameaca_proxima_verificacao=now)
        consulta.return_value = [{"state": "NO_MATCH", "checked_at": now, "expires_at": now + timedelta(minutes=10)}]
        verificar_links_salvos()
        self.link.refresh_from_db()
        self.assertEqual(self.link.ameaca_estado, "NO_MATCH")
        self.assertFalse(self.link.ameaca_notificada)
        self.assertLessEqual(self.link.ameaca_proxima_verificacao, now + timedelta(minutes=10, seconds=1))

    def test_alterar_url_descarta_classificacao_anterior(self):
        ProjectLink.objects.filter(pk=self.link.pk).update(ameaca_estado="THREAT", ameaca_notificada=True)
        self.link.url = "https://example.org/"
        self.link.save()
        self.link.refresh_from_db()
        self.assertEqual(self.link.ameaca_estado, "UNVERIFIED")
        self.assertFalse(self.link.ameaca_notificada)


    @patch("plataforma.guardiao_consulta.consultar_links", return_value={})
    def test_alerta_expira_e_nao_expoe_classificacao_antiga(self, consulta):
        from datetime import timedelta
        from django.utils import timezone

        self.client.force_login(self.user)
        now = timezone.now()
        ProjectLink.objects.filter(pk=self.link.pk).update(
            ameaca_estado="THREAT", ameaca_verificada_em=now, ameaca_expira_em=now + timedelta(minutes=5))
        page = self.client.get(reverse("plataforma:project_detail", args=[self.project.pk]))
        self.assertContains(page, "Possível ameaça")
        self.assertNotContains(page, 'href="https://example.com/"')
        ProjectLink.objects.filter(pk=self.link.pk).update(ameaca_verificada_em=now - timedelta(minutes=31))
        page = self.client.get(reverse("plataforma:project_detail", args=[self.project.pk]))
        self.assertNotContains(page, "Possível ameaça")
        self.assertContains(page, 'class="link-status link-status--security"')
        self.assertContains(page, "Segurança não verificada")
        self.assertContains(page, 'href="https://example.com/"')
