from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.core.validators import FileExtensionValidator




class PerfilInstitucionalForm(forms.ModelForm):
    """Dados básicos que o aluno pode alterar no próprio perfil."""

    avatar = forms.FileField(
        label="Foto de perfil",
        required=False,
        validators=[
            FileExtensionValidator(
                allowed_extensions=("jpg", "jpeg", "png", "webp"),
                message="Envie uma imagem JPG, PNG ou WEBP.",
            )
        ],
        help_text="JPG, PNG ou WEBP, até 3 MB.",
        widget=forms.ClearableFileInput(
            attrs={"accept": "image/jpeg,image/png,image/webp"}
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
        from PIL import Image
        from plataforma.validators import normalizar_logo
        import uuid
        try:
            image = Image.open(avatar)
            image.verify()
            avatar.seek(0)
            image = Image.open(avatar)
            if min(image.size) < 16 or max(image.size) > 4096 or getattr(image, "n_frames", 1) != 1:
                raise ValueError("Dimensões ou animação inválidas")
            avatar.seek(0)
            return normalizar_logo(avatar, f"{uuid.uuid4().hex}.webp", max_dimension=1280)
        except Exception as exc:
            raise forms.ValidationError("Envie uma imagem estática válida, de 16 até 4.096 pixels.") from exc



class SenhaInstitucionalForm(PasswordChangeForm):
    """Troca de senha com os campos e mensagens em português."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Senha atual"
        self.fields["new_password1"].label = "Nova senha"
        self.fields["new_password2"].label = "Confirme a nova senha"
        self.fields["old_password"].widget.attrs["autocomplete"] = "current-password"
        self.fields["new_password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["new_password2"].widget.attrs["autocomplete"] = "new-password"
