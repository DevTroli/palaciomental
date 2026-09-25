from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import MemberProfile, Project

User = get_user_model()


class MemberCreationForm(UserCreationForm):
    email = forms.EmailField(label="E-mail", required=True)
    first_name = forms.CharField(label="Nome", max_length=150)

    class Meta:
        model = User
        fields = ("first_name", "username", "email", "password1", "password2")
        labels = {"username": "Nome de usuário"}

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Este e-mail já está cadastrado.")
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = MemberProfile
        fields = ("bio",)
        widgets = {"bio": forms.Textarea(attrs={"rows": 4, "maxlength": 280, "placeholder": "Conte brevemente o que você cria."})}


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("title", "direction", "status", "visibility", "category", "tags")
        widgets = {
            "direction": forms.Textarea(attrs={"rows": 5, "placeholder": "Por que este projeto existe? Que transformação você quer construir?"}),
            "tags": forms.TextInput(attrs={"placeholder": "educação, pesquisa, criatividade"}),
        }

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 3:
            raise forms.ValidationError("Use um título com pelo menos 3 caracteres.")
        return title

    def clean_category(self):
        category = self.cleaned_data["category"].strip()
        if not category:
            raise forms.ValidationError("Informe uma categoria para facilitar a descoberta.")
        return category
