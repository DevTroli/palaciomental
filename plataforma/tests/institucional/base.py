import hashlib
from io import BytesIO
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from plataforma.models import ConviteGrupo, ConviteOrganizacao, DominioOrganizacao, Grupo, IdentidadeOrganizacao, MembroGrupo, MembroOrganizacao, MembroTurma, Organizacao, ProgramaInstitucional, Project, SolicitacaoGrupo, SolicitacaoTurma, Turma, VinculoProjetoInstitucional
from plataforma.services import ativar_organizacao


User = get_user_model()


@override_settings(
    ALLOWED_HOSTS=["testserver", ".palaciomental.com.br", ".app.github.dev"],
    PALACIO_BASE_DOMAIN="palaciomental.com.br",
    TENANT_RESERVED_HOSTS=["www", "api", "status", "admin", "app"],
)
class PortalInstitucionalBase(TestCase):
    def setUp(self):
        self.organization = Organizacao.objects.create(slug="camppg", nome="CAMPPG", status=Organizacao.STATUS_ATIVA)
        DominioOrganizacao.objects.create(
            organizacao=self.organization,
            hostname="camppg.palaciomental.com.br",
            principal=True,
        )
        self.user = User.objects.create_user(
            username="participante",
            email="participante@example.com",
            password="Senha-forte-123",
        )
        self.pm_staff = User.objects.create_user(
            username="pm-staff",
            email="pm-staff@example.com",
            password="Senha-forte-123",
            is_staff=True,
        )

    def make_group(self, programa, nome, criado_por=None, professor=None):
        turma = Turma.objects.create(
            programa=programa,
            nome=f"Turma de {nome}",
            criado_por=criado_por or self.user,
            professor_responsavel=professor,
        )
        return Grupo.objects.create(turma=turma, nome=nome, criado_por=criado_por or self.user)

    def logo_file(self, name="logo.png", size=(320, 120), image_format="PNG"):
        buffer = BytesIO()
        mode = "RGB" if image_format.upper() in {"JPEG", "JPG"} else "RGBA"
        Image.new(mode, size, (110, 74, 163, 255) if mode == "RGBA" else (110, 74, 163)).save(buffer, format=image_format)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{image_format.lower()}")
