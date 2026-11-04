from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.core.validators import FileExtensionValidator
from django.db.models import Q

from plataforma.models import Project

from .models import EventoCalendario


class CampPerfilForm(forms.ModelForm):
    """Dados básicos que o aluno pode alterar no próprio perfil."""

    avatar = forms.FileField(
        label="Foto de perfil",
        required=False,
        validators=[
            FileExtensionValidator(
                allowed_extensions=("jpg", "jpeg", "png", "webp", "gif"),
                message="Envie uma imagem JPG, PNG, WEBP ou GIF.",
            )
        ],
        help_text="JPG, PNG, WEBP ou GIF, até 3 MB.",
        widget=forms.ClearableFileInput(
            attrs={"accept": "image/jpeg,image/png,image/webp,image/gif"}
        ),
    )

    remover_avatar = forms.BooleanField(
        label="Remover foto atual",
        required=False,
    )

    class Meta:
        model = get_user_model()
        fields = ("first_name", "last_name", "email")
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "placeholder": "Seu nome",
                    "maxlength": 150,
                    "autocomplete": "given-name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "placeholder": "Seu sobrenome",
                    "maxlength": 150,
                    "autocomplete": "family-name",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "voce@exemplo.com",
                    "autocomplete": "email",
                }
            ),
        }

    def clean_first_name(self):
        nome = (self.cleaned_data.get("first_name") or "").strip()
        if len(nome) < 2:
            raise forms.ValidationError("Informe seu nome com pelo menos 2 caracteres.")
        return nome

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            return email
        duplicados = get_user_model().objects.filter(email__iexact=email)
        if self.instance.pk:
            duplicados = duplicados.exclude(pk=self.instance.pk)
        if duplicados.exists():
            raise forms.ValidationError("Este e-mail já está em uso por outra conta.")
        return email

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if not avatar:
            return avatar
        if avatar.size > 3 * 1024 * 1024:
            raise forms.ValidationError("A imagem deve ter no máximo 3 MB.")
        content_type = getattr(avatar, "content_type", "") or ""
        if content_type and not content_type.startswith("image/"):
            raise forms.ValidationError("Envie um arquivo de imagem válido.")
        return avatar


class CampSenhaForm(PasswordChangeForm):
    """Troca de senha com os campos e mensagens em português."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Senha atual"
        self.fields["new_password1"].label = "Nova senha"
        self.fields["new_password2"].label = "Confirme a nova senha"
        self.fields["old_password"].widget.attrs["autocomplete"] = "current-password"
        self.fields["new_password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["new_password2"].widget.attrs["autocomplete"] = "new-password"


class CampProjectForm(forms.ModelForm):
    """Formulário de projeto do CAMP, com validações próprias do ambiente."""

    class Meta:
        model = Project
        fields = (
            "title",
            "direction",
            "category",
            "status",
            "visibility",
            "tags",
            "seeking_collaborators",
            "collaboration_description",
        )
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Dê um nome ao seu projeto", "maxlength": 140}),
            "direction": forms.Textarea(
                attrs={
                    "rows": 5,
                    "maxlength": 1000,
                    "placeholder": "Por que este projeto existe? Que transformação você quer construir?",
                }
            ),
            "category": forms.TextInput(attrs={"placeholder": "Ex.: Educação, pesquisa ou produto", "maxlength": 80}),
            "tags": forms.TextInput(attrs={"placeholder": "educação, pesquisa, criatividade"}),
            "collaboration_description": forms.TextInput(
                attrs={"placeholder": "Ex.: pessoa para pesquisa e prototipação", "maxlength": 280}
            ),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner or getattr(self.instance, "owner", None)
        self.fields["status"].choices = (
            (Project.STATUS_IDEA, "Em planejamento"),
            (Project.STATUS_ACTIVE, "Em desenvolvimento"),
            (Project.STATUS_PAUSED, "Pausado"),
            (Project.STATUS_DONE, "Concluído"),
        )

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if len(title) < 3:
            raise forms.ValidationError("Use um título com pelo menos 3 caracteres.")
        if self.owner:
            duplicados = Project.objects.filter(owner=self.owner, title__iexact=title)
            if self.instance.pk:
                duplicados = duplicados.exclude(pk=self.instance.pk)
            if duplicados.exists():
                raise forms.ValidationError("Você já possui um projeto com este título. Escolha outro nome.")
        return title

    def clean_category(self):
        category = (self.cleaned_data.get("category") or "").strip()
        if not category:
            raise forms.ValidationError("Informe uma categoria para facilitar a descoberta.")
        return category

    def clean_tags(self):
        tags = [tag.strip() for tag in (self.cleaned_data.get("tags") or "").split(",") if tag.strip()]
        if len(tags) > 8:
            raise forms.ValidationError("Use no máximo 8 tags.")
        if any(len(tag) > 24 for tag in tags):
            raise forms.ValidationError("Cada tag deve ter no máximo 24 caracteres.")
        return ", ".join(tags)

    def clean_visibility(self):
        return self.cleaned_data.get("visibility") or Project.VISIBILITY_PRIVATE


class CampEventoForm(forms.ModelForm):
    """Evento pessoal do calendário, criado e mantido pelo próprio aluno."""

    class Meta:
        model = EventoCalendario
        fields = ("titulo", "descricao", "tipo", "data", "horario", "projeto")
        widgets = {
            "titulo": forms.TextInput(
                attrs={"placeholder": "Ex.: Revisão do projeto com o grupo", "maxlength": 140}
            ),
            "descricao": forms.Textarea(
                attrs={
                    "rows": 4,
                    "maxlength": 500,
                    "placeholder": "Detalhes, links ou combinados importantes para este evento.",
                }
            ),
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "horario": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, aluno=None, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.aluno = aluno
        self.organizacao = organizacao
        self.fields["horario"].required = False
        self.fields["projeto"].required = False
        self.fields["projeto"].empty_label = "Sem projeto vinculado"
        self.fields["projeto"].queryset = (
            Project.objects.filter(organizacao=organizacao)
            .filter(Q(owner=aluno) | Q(memberships__user=aluno))
            .distinct()
            .order_by("title")
            if aluno and organizacao
            else Project.objects.none()
        )

    def clean_titulo(self):
        titulo = (self.cleaned_data.get("titulo") or "").strip()
        if len(titulo) < 3:
            raise forms.ValidationError("Use um título com pelo menos 3 caracteres.")
        return titulo

    def clean(self):
        cleaned = super().clean()
        titulo = cleaned.get("titulo")
        tipo = cleaned.get("tipo")
        data = cleaned.get("data")
        if not (self.aluno and self.organizacao and titulo and tipo and data):
            return cleaned

        duplicados = EventoCalendario.objects.filter(
            organizacao=self.organizacao,
            aluno=self.aluno,
            tipo=tipo,
            titulo__iexact=titulo,
            data=data,
        )
        if self.instance.pk:
            duplicados = duplicados.exclude(pk=self.instance.pk)
        if duplicados.exists():
            raise forms.ValidationError(
                "Você já tem um evento com este título nesta data. Escolha outro nome."
            )
        return cleaned

    def save(self, commit=True):
        evento = super().save(commit=False)
        if evento.tipo == EventoCalendario.TIPO_ATIVIDADE:
            evento.status = EventoCalendario.STATUS_CONFIRMADO
        elif evento.pk is None or evento.status == EventoCalendario.STATUS_CONFIRMADO:
            evento.status = EventoCalendario.STATUS_PENDENTE
        if commit:
            evento.save()
        return evento
