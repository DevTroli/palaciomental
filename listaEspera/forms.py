from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import CollaborationRequest, MemberProfile, Project, ProjectComment, ProjectLink, ProjectMilestone

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
        fields = ("title", "direction", "status", "visibility", "category", "tags", "seeking_collaborators", "collaboration_description", "collaboration_tags")
        widgets = {
            "direction": forms.Textarea(attrs={"rows": 5, "placeholder": "Por que este projeto existe? Que transformação você quer construir?"}),
            "tags": forms.TextInput(attrs={"placeholder": "educação, pesquisa, criatividade"}),
            "collaboration_description": forms.TextInput(attrs={"placeholder": "Ex.: pessoa para pesquisa e prototipação"}),
            "collaboration_tags": forms.TextInput(attrs={"placeholder": "pesquisa, design, desenvolvimento"}),
        }

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 3:
            raise forms.ValidationError("Use um título com pelo menos 3 caracteres.")
        return title

    def clean_visibility(self):
        return self.cleaned_data.get("visibility") or Project.VISIBILITY_PRIVATE
    def clean_category(self):
        category = self.cleaned_data["category"].strip()
        if not category:
            raise forms.ValidationError("Informe uma categoria para facilitar a descoberta.")
        return category


class CommentForm(forms.ModelForm):
    class Meta:
        model = ProjectComment
        fields = ("content",)
        labels = {"content": "Comentário"}
        widgets = {"content": forms.Textarea(attrs={"rows": 3, "maxlength": 2000, "placeholder": "Compartilhe um contexto útil sobre este projeto."})}


class MilestoneForm(forms.ModelForm):
    class Meta:
        model = ProjectMilestone
        fields = ("title", "description", "milestone_type")
        labels = {"title": "Título do marco", "description": "O que mudou?", "milestone_type": "Tipo de avanço"}
        widgets = {"description": forms.Textarea(attrs={"rows": 3, "maxlength": 1000})}


class CollaborationRequestForm(forms.ModelForm):
    class Meta:
        model = CollaborationRequest
        fields = ("message",)
        labels = {"message": "Como você pode contribuir?"}
        widgets = {"message": forms.Textarea(attrs={"rows": 3, "maxlength": 500, "placeholder": "Conte brevemente seu interesse e como pode ajudar."})}

class ProjectBasicsForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("title", "direction", "status", "visibility")
        widgets = {"direction": forms.Textarea(attrs={"rows": 4, "placeholder": "Qual é o rumo deste projeto? Comece com uma frase clara."})}
    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 3:
            raise forms.ValidationError("Use um título com pelo menos 3 caracteres.")
        return title

class ProjectContextForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visibility"].required = False

    class Meta:
        model = Project
        fields = ("category", "tags", "seeking_collaborators", "collaboration_description", "collaboration_tags", "visibility")
        widgets = {
            "category": forms.TextInput(attrs={"placeholder": "Ex.: Educação, pesquisa ou produto"}),
            "tags": forms.TextInput(attrs={"placeholder": "até 8 tags, separadas por vírgula"}),
            "collaboration_description": forms.TextInput(attrs={"placeholder": "Ex.: pesquisa e prototipação"}),
            "collaboration_tags": forms.TextInput(attrs={"placeholder": "até 8 tags, separadas por vírgula"}),
        }
    def _clean_tags(self, value, label):
        tags = [tag.strip() for tag in (value or "").split(",") if tag.strip()]
        if len(tags) > 8:
            raise forms.ValidationError(f"Use no máximo 8 {label}.")
        if any(len(tag) > 24 for tag in tags):
            raise forms.ValidationError(f"Cada {label[:-1]} deve ter no máximo 24 caracteres.")
        return ", ".join(tags)
    def clean_tags(self):
        return self._clean_tags(self.cleaned_data.get("tags"), "tags")
    def clean_collaboration_tags(self):
        return self._clean_tags(self.cleaned_data.get("collaboration_tags"), "tags de colaboração")
    def clean_visibility(self):
        return self.cleaned_data.get("visibility") or Project.VISIBILITY_PRIVATE
    def clean_category(self):
        category = (self.cleaned_data.get("category") or "").strip()
        if len(category) > 60:
            raise forms.ValidationError("A categoria deve ter no máximo 60 caracteres.")
        return category

class ProjectLinkForm(forms.ModelForm):
    class Meta:
        model = ProjectLink
        fields = ("label", "url")
        widgets = {"label": forms.TextInput(attrs={"placeholder": "Ex.: Documento de visão"}), "url": forms.URLInput(attrs={"placeholder": "https://..."})}
    def clean_label(self):
        return self.cleaned_data["label"].strip()

ProjectLinkFormSet = inlineformset_factory(Project, ProjectLink, form=ProjectLinkForm, extra=1, can_delete=True, max_num=12, validate_max=True)
