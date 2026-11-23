from datetime import date
from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import override_settings
from PIL import Image

from plataforma.models import DominioOrganizacao, EventoCalendario, MemberProfile, MembroOrganizacao, Organizacao, Project
from .base import PortalInstitucionalBase

HOST = "camppg.palaciomental.com.br"


class ExperienceM6Tests(PortalInstitucionalBase):
    def setUp(self):
        super().setUp()
        self.membership = MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.user)
        self.other = Organizacao.objects.create(nome="Outra escola", slug="outra", status="ativa")
        DominioOrganizacao.objects.create(organizacao=self.other, hostname="outra.palaciomental.com.br", principal=True)
        self.client.force_login(self.user)


    def test_people_search_accepts_at_username_and_stays_in_tenant(self):
        user = get_user_model().objects.create_user(username="ana123", first_name="Ana")
        outsider = get_user_model().objects.create_user(username="ana_externa", first_name="Ana")
        MembroOrganizacao.objects.create(organizacao=self.organization, usuario=user)
        MembroOrganizacao.objects.create(organizacao=self.other, usuario=outsider)
        response = self.client.get("/projetos/", {"vista": "alunos", "q": "@ana123"}, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ana123")
        self.assertNotContains(response, "ana_externa")
        self.assertContains(response, 'name="vista"')


    def test_agenda_rejects_other_tenant_and_forged_project(self):
        event = EventoCalendario.objects.create(organizacao=self.other, aluno=self.user,
            titulo="Segredo da outra escola", tipo="trabalho", origem="aluno", data=date.today())
        response = self.client.get("/calendario/", HTTP_HOST=HOST)
        self.assertNotContains(response, event.titulo)
        for action in ("editar", "excluir", "entregar"):
            self.assertEqual(self.client.post(f"/calendario/{event.pk}/{action}/", HTTP_HOST=HOST).status_code, 404)
        external_project = Project.objects.create(owner=self.user, organizacao=self.other, title="Externo")
        response = self.client.post("/calendario/novo/", {"titulo": "Evento forjado", "tipo": "trabalho",
            "data": date.today().isoformat(), "projeto": external_project.pk}, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventoCalendario.objects.filter(titulo="Evento forjado").exists())


    def test_manager_publishes_activity_to_active_member_without_granting_edit_permission(self):
        membership = MembroOrganizacao.objects.create(organizacao=self.organization, usuario=self.pm_staff, papel="gestor")
        self.client.force_login(self.pm_staff)
        response = self.client.post("/calendario/publicar/", {"titulo": "Oficina institucional", "tipo": "atividade",
            "data": date.today().isoformat(), "destinatario": self.membership.pk}, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 302)
        event = EventoCalendario.objects.get(titulo="Oficina institucional")
        self.assertEqual(event.origem, "organizacao")
        self.assertEqual(event.aluno, self.user)
        self.client.force_login(self.user)
        self.assertContains(self.client.get("/calendario/", HTTP_HOST=HOST), event.titulo)
        self.assertEqual(self.client.post(f"/calendario/{event.pk}/excluir/", HTTP_HOST=HOST).status_code, 404)
        self.assertEqual(self.client.post("/calendario/publicar/", HTTP_HOST=HOST).status_code, 403)


    def test_avatar_rejects_fake_image_and_normalizes_real_image(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            payload = {"form": "perfil", "first_name": "Participante", "email": self.user.email}
            response = self.client.post("/perfil/", {**payload, "avatar": SimpleUploadedFile("fake.png", b"not-image", content_type="image/png")}, HTTP_HOST=HOST)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(MemberProfile.objects.get(user=self.user).avatar)
            data = BytesIO()
            Image.new("RGB", (100, 100), "blue").save(data, format="PNG")
            response = self.client.post("/perfil/", {**payload, "avatar": SimpleUploadedFile("real.png", data.getvalue(), content_type="image/png")}, HTTP_HOST=HOST)
            self.assertEqual(response.status_code, 302)
            avatar = MemberProfile.objects.get(user=self.user).avatar
            self.assertTrue(avatar.name.endswith(".webp"))
            with avatar.open("rb") as stream:
                self.assertEqual(Image.open(stream).format, "WEBP")

    def test_avatar_removal_is_confirmed_on_save_and_survives_validation_errors(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            data = BytesIO()
            Image.new("RGB", (100, 100), "blue").save(data, format="PNG")
            payload = {"form": "perfil", "first_name": "Participante", "email": self.user.email}
            self.client.post("/perfil/", {**payload, "avatar": SimpleUploadedFile("real.png", data.getvalue(), content_type="image/png")}, HTTP_HOST=HOST)
            response = self.client.post("/perfil/", {**payload, "first_name": "x", "remover_avatar": "on"}, HTTP_HOST=HOST)
            self.assertContains(response, 'id="id_remover_avatar"')
            self.assertTrue(response.context["form_perfil"]["remover_avatar"].value())
            self.assertTrue(MemberProfile.objects.get(user=self.user).avatar)
            self.assertEqual(self.client.post("/perfil/", {**payload, "remover_avatar": "on"}, HTTP_HOST=HOST).status_code, 302)
            self.assertFalse(MemberProfile.objects.get(user=self.user).avatar)
            self.assertNotContains(self.client.get("/perfil/?aba=configuracoes", HTTP_HOST=HOST), 'id="id_remover_avatar"')

    def test_registration_rejects_username_ignoring_letter_case(self):
        from plataforma.forms import MemberCreationForm
        form = MemberCreationForm(data={"username": self.user.username.upper(), "first_name": "Pessoa", "email": "novo@example.com", "password1": "Senha-forte-123", "password2": "Senha-forte-123"})
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)


    def test_inactive_membership_cannot_use_new_agenda(self):
        self.membership.status = "suspensa"
        self.membership.save()
        self.assertEqual(self.client.post("/calendario/novo/", HTTP_HOST=HOST).status_code, 403)

    def test_agenda_posts_require_csrf(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post("/calendario/novo/", HTTP_HOST=HOST).status_code, 403)

    def test_existing_event_does_not_reveal_project_that_became_private(self):
        private = Project.objects.create(owner=self.pm_staff, organizacao=self.organization,
                                         title="Título privado oculto", visibility="privado")
        EventoCalendario.objects.create(organizacao=self.organization, aluno=self.user,
            titulo="Compromisso existente", projeto=private, data=date.today())
        for path in ("/calendario/", "/perfil/", "/caixa-de-entrada/"):
            self.assertNotContains(self.client.get(path, HTTP_HOST=HOST), private.title)

    def test_password_change_preserves_authenticated_session(self):
        response = self.client.post("/perfil/", {"form": "senha", "old_password": "Senha-forte-123",
            "new_password1": "NovaSenha-M6-456!", "new_password2": "NovaSenha-M6-456!"}, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NovaSenha-M6-456!"))
        self.assertEqual(self.client.get("/perfil/", HTTP_HOST=HOST).status_code, 200)

    def test_manager_cannot_publish_to_member_of_another_tenant(self):
        self.membership.papel = "gestor"
        self.membership.save()
        external = MembroOrganizacao.objects.create(organizacao=self.other, usuario=self.pm_staff)
        response = self.client.post("/calendario/publicar/", {"titulo": "Publicação forjada", "tipo": "atividade",
            "data": date.today().isoformat(), "destinatario": external.pk}, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventoCalendario.objects.filter(titulo="Publicação forjada").exists())


    def test_login_navigation_and_logout_survive_unavailable_session_cache(self):
        from unittest.mock import patch
        from django.core.cache import caches
        from redis.exceptions import ConnectionError
        cache = caches["default"]
        with patch.object(cache, "get", side_effect=ConnectionError), patch.object(cache, "set", side_effect=ConnectionError), patch.object(cache, "delete", side_effect=ConnectionError):
            self.assertEqual(self.client.get("/perfil/", HTTP_HOST=HOST).status_code, 200)
            self.client.post("/sair/", HTTP_HOST=HOST)
            response = self.client.post("/entrar/", {"username": self.user.username, "password": "Senha-forte-123"}, HTTP_HOST=HOST)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(self.client.get("/perfil/", HTTP_HOST=HOST).status_code, 200)
            self.assertEqual(self.client.post("/sair/", HTTP_HOST=HOST).status_code, 302)
            self.assertNotIn("_auth_user_id", self.client.session)
