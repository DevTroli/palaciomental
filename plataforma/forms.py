from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q

from .models import CollaborationRequest, ConviteGrupo, ConviteOrganizacao, Grupo, IdentidadeOrganizacao, MemberProfile, MembroOrganizacao, MembroTurma, ProgramaInstitucional, Project, ProjectComment, ProjectLink, ProjectMilestone, SolicitacaoGrupo, SolicitacaoTurma, Turma

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


class IdentidadeOrganizacaoForm(forms.ModelForm):
    class Meta:
        model = IdentidadeOrganizacao
        fields = ("nome_exibicao", "logo", "cor_primaria", "cor_destaque", "cor_fundo")
        labels = {
            "nome_exibicao": "Nome mostrado no ambiente",
            "logo": "Logo da organização",
            "cor_primaria": "Cor principal",
            "cor_destaque": "Cor de destaque",
            "cor_fundo": "Cor de fundo",
        }
        widgets = {"logo": forms.ClearableFileInput(attrs={"accept": ".png,.jpg,.jpeg,.webp"})}


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("title", "direction", "status", "visibility", "category", "tags", "seeking_collaborators", "collaboration_description")
        widgets = {
            "direction": forms.Textarea(attrs={"rows": 5, "placeholder": "Por que este projeto existe? Que transformação você quer construir?"}),
            "tags": forms.TextInput(attrs={"placeholder": "educação, pesquisa, criatividade"}),
            "collaboration_description": forms.TextInput(attrs={"placeholder": "Ex.: pessoa para pesquisa e prototipação"}),
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
    def __init__(self, *args, owner=None, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project_owner = owner or getattr(self.instance, "owner", None)
        if organizacao is not None:
            self.fields["tipo_projeto"] = forms.ChoiceField(label="Tipo de projeto", choices=(("autonomo", "Projeto autônomo"), ("programa", "Projeto vinculado a programa")), help_text="Projeto autônomo não exige turma. Projeto de programa exige turma e professor orientador.")
            self.fields["turma"] = forms.ModelChoiceField(label="Turma", required=False, queryset=Turma.objects.none())
            self.fields["grupo"] = forms.ModelChoiceField(label="Grupo (opcional)", required=False, queryset=Grupo.objects.none())
            self.fields["orientador"] = forms.ModelChoiceField(label="Professor orientador", required=False, queryset=User.objects.none())
            afiliacao = MembroOrganizacao.objects.filter(organizacao=organizacao, usuario=owner).first() if owner else None
            turmas = Turma.objects.filter(programa__organizacao=organizacao, status=Turma.STATUS_ATIVO)
            if afiliacao and afiliacao.papel not in {MembroOrganizacao.PAPEL_PROPRIETARIO, MembroOrganizacao.PAPEL_GESTOR}:
                turmas = turmas.filter(Q(membros__usuario=owner, membros__status=MembroTurma.STATUS_ATIVO) | Q(professor_responsavel=owner)).distinct()
            self.fields["turma"].queryset = turmas.select_related("programa", "professor_responsavel")
            self.fields["grupo"].queryset = Grupo.objects.filter(turma__in=turmas, status=Grupo.STATUS_ATIVO).select_related("turma")
            self.fields["orientador"].queryset = User.objects.filter(
                turmas_orientadas__programa__organizacao=organizacao,
                afiliacoes_organizacionais__organizacao=organizacao,
                afiliacoes_organizacionais__papel=MembroOrganizacao.PAPEL_PROFESSOR,
                afiliacoes_organizacionais__status=MembroOrganizacao.STATUS_ATIVA,
            ).distinct()
            vinculo = getattr(self.instance, "vinculo_institucional", None)
            if vinculo is not None:
                self.initial.update(tipo_projeto="programa", turma=vinculo.turma_id, grupo=vinculo.grupo_id, orientador=vinculo.orientador_id)
            else:
                self.initial.setdefault("tipo_projeto", "autonomo")

    class Meta:
        model = Project
        fields = ("title", "direction", "status", "visibility")
        widgets = {"direction": forms.Textarea(attrs={"rows": 4, "placeholder": "Qual é o rumo deste projeto? Comece com uma frase clara."})}

    def clean(self):
        cleaned = super().clean()
        if "tipo_projeto" not in self.fields or cleaned.get("tipo_projeto") == "autonomo":
            cleaned["turma"], cleaned["grupo"], cleaned["orientador"] = None, None, None
            return cleaned
        turma, grupo, orientador = cleaned.get("turma"), cleaned.get("grupo"), cleaned.get("orientador")
        if turma is None:
            self.add_error("turma", "Escolha a turma do projeto de programa.")
        if orientador is None:
            self.add_error("orientador", "Escolha o professor orientador.")
        elif turma and turma.professor_responsavel_id != orientador.pk:
            self.add_error("orientador", "O professor precisa ser o responsável pela turma selecionada.")
        if grupo is not None and turma is not None and grupo.turma_id != turma.pk:
            self.add_error("grupo", "O grupo precisa pertencer à turma selecionada.")
        return cleaned
    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 3:
            raise forms.ValidationError("Use um título com pelo menos 3 caracteres.")
        if self.project_owner and Project.objects.filter(owner=self.project_owner, title__iexact=title).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Você já possui um projeto com este título. Escolha outro nome para não confundir os projetos.")
        return title

class ProjectContextForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visibility"].required = False

    class Meta:
        model = Project
        fields = ("category", "tags", "seeking_collaborators", "collaboration_description", "visibility")
        widgets = {
            "category": forms.TextInput(attrs={"placeholder": "Ex.: Educação, pesquisa ou produto"}),
            "tags": forms.TextInput(attrs={"placeholder": "até 8 tags, separadas por vírgula"}),
            "collaboration_description": forms.Textarea(attrs={"rows": 3, "placeholder": "Ex.: buscamos alguém para pesquisa e prototipação"}),
            "seeking_collaborators": forms.CheckboxInput(attrs={"class": "collaboration-check"}),
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


class ProgramaInstitucionalForm(forms.ModelForm):
    class Meta:
        model = ProgramaInstitucional
        fields = ("nome", "descricao", "status")
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4, "placeholder": "Qual é o propósito deste programa?"}),
        }

    def clean_nome(self):
        nome = self.cleaned_data["nome"].strip()
        if len(nome) < 3:
            raise forms.ValidationError("Use um nome com pelo menos 3 caracteres.")
        return nome


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ("nome", "descricao", "professor_responsavel", "politica_participacao", "status")
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4, "placeholder": "Qual é o ciclo ou unidade de orientação desta turma?"}),
        }

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organizacao is not None:
            self.fields["professor_responsavel"].queryset = User.objects.filter(
                afiliacoes_organizacionais__organizacao=organizacao,
                afiliacoes_organizacionais__papel=MembroOrganizacao.PAPEL_PROFESSOR,
                afiliacoes_organizacionais__status=MembroOrganizacao.STATUS_ATIVA,
            ).distinct()

    def clean_nome(self):
        nome = self.cleaned_data["nome"].strip()
        if len(nome) < 2:
            raise forms.ValidationError("Use um nome com pelo menos 2 caracteres.")
        return nome


class GrupoForm(forms.ModelForm):
    class Meta:
        model = Grupo
        fields = ("nome", "descricao", "aberto_para_entrada", "status")
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4, "placeholder": "Qual é o objetivo deste grupo?"}),
        }

    def clean_nome(self):
        nome = self.cleaned_data["nome"].strip()
        if len(nome) < 2:
            raise forms.ValidationError("Use um nome com pelo menos 2 caracteres.")
        return nome


class SolicitacaoTurmaForm(forms.ModelForm):
    class Meta:
        model = SolicitacaoTurma
        fields = ("mensagem",)
        labels = {"mensagem": "Mensagem (opcional)"}
        widgets = {"mensagem": forms.Textarea(attrs={"rows": 3, "placeholder": "Explique brevemente por que deseja participar."})}


class SolicitacaoGrupoForm(forms.ModelForm):
    class Meta:
        model = SolicitacaoGrupo
        fields = ("mensagem",)
        labels = {"mensagem": "Mensagem (opcional)"}
        widgets = {"mensagem": forms.Textarea(attrs={"rows": 3, "placeholder": "Explique brevemente seu interesse no grupo."})}


class ConviteGrupoForm(forms.ModelForm):
    class Meta:
        model = ConviteGrupo
        fields = ("email",)
        labels = {"email": "E-mail da pessoa"}

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class ConviteOrganizacaoForm(forms.ModelForm):
    class Meta:
        model = ConviteOrganizacao
        fields = ("email", "papel")
        labels = {"email": "E-mail da pessoa", "papel": "Papel inicial"}
        help_texts = {"email": "A pessoa receberá um link de uso único para entrar no ambiente."}

    def __init__(self, *args, papeis_permitidos=None, **kwargs):
        super().__init__(*args, **kwargs)
        permitidos = papeis_permitidos or []
        self.fields["papel"].choices = [choice for choice in MembroOrganizacao.PAPEL_CHOICES if choice[0] in permitidos]

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
