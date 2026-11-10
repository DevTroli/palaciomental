from django import forms
from django.db.models import Q

from .models import EventoCalendario, Project, MembroOrganizacao


class EventoInstitucionalForm(forms.ModelForm):
    """Compromisso pessoal de um afiliado; nunca aceita tenant/aluno do POST."""

    class Meta:
        model = EventoCalendario
        fields = ("titulo", "descricao", "tipo", "data", "horario", "projeto")
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "horario": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "descricao": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, organizacao, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.organizacao, self.usuario = organizacao, usuario
        self.instance.organizacao = organizacao
        self.instance.aluno = usuario
        self.fields["projeto"].queryset = Project.objects.filter(organizacao=organizacao).filter(
            Q(owner=usuario) | Q(memberships__user=usuario, visibility=Project.VISIBILITY_PUBLIC)
        ).distinct().order_by("title")

    def clean_titulo(self):
        title = self.cleaned_data["titulo"].strip()
        if len(title) < 3:
            raise forms.ValidationError("Informe um título com pelo menos 3 caracteres.")
        return title

    def clean(self):
        data = super().clean() or {}
        if all(data.get(k) for k in ("titulo", "tipo", "data")):
            existing = EventoCalendario.objects.filter(
                organizacao=self.organizacao, aluno=self.usuario,
                titulo__iexact=data["titulo"], tipo=data["tipo"], data=data["data"],
            ).exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError("Você já tem um evento com este título nesta data.")
        return data

    def save(self, commit=True):
        event = super().save(commit=False)
        event.organizacao, event.aluno = self.organizacao, self.usuario
        event.origem = EventoCalendario.ORIGEM_ALUNO
        if event.tipo == EventoCalendario.TIPO_ATIVIDADE:
            event.status = EventoCalendario.STATUS_CONFIRMADO
        elif event.status == EventoCalendario.STATUS_CONFIRMADO:
            event.status = EventoCalendario.STATUS_PENDENTE
        if commit:
            event.save()
        return event


class PublicacaoAtividadeForm(EventoInstitucionalForm):
    destinatario = forms.ModelChoiceField(label="Participante", queryset=MembroOrganizacao.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destinatario"].queryset = MembroOrganizacao.objects.filter(
            organizacao=self.organizacao, status=MembroOrganizacao.STATUS_ATIVA
        ).select_related("usuario")
        self.fields["projeto"].queryset = Project.objects.filter(
            organizacao=self.organizacao, visibility=Project.VISIBILITY_PUBLIC
        ).order_by("title")

    def clean(self):
        membership = self.cleaned_data.get("destinatario")
        if membership:
            self.usuario = membership.usuario
            self.instance.aluno = membership.usuario
        return super().clean()

    def save(self, commit=True):
        event = super().save(commit=False)
        event.origem = EventoCalendario.ORIGEM_ORGANIZACAO
        if commit:
            event.save()
        return event
