from django.conf import settings
from django.db import models


class EventoCalendario(models.Model):
    """Compromisso do calendário de um aluno do CAMP.

    Reúne dois tipos de item: atividades (encontros, aulas, oficinas) e
    trabalhos com prazo de entrega. Cada evento pertence a uma organização e
    a um aluno, podendo estar vinculado a um projeto.
    """

    TIPO_ATIVIDADE = "atividade"
    TIPO_TRABALHO = "trabalho"
    TIPO_CHOICES = (
        (TIPO_ATIVIDADE, "Atividade"),
        (TIPO_TRABALHO, "Trabalho"),
    )

    STATUS_PENDENTE = "pendente"
    STATUS_ENTREGUE = "entregue"
    STATUS_CONFIRMADO = "confirmado"
    STATUS_CHOICES = (
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_ENTREGUE, "Entregue"),
        (STATUS_CONFIRMADO, "Confirmada"),
    )

    ORIGEM_ALUNO = "aluno"
    ORIGEM_ORGANIZACAO = "organizacao"
    ORIGEM_CHOICES = (
        (ORIGEM_ALUNO, "Criado pelo aluno"),
        (ORIGEM_ORGANIZACAO, "Organização"),
    )

    organizacao = models.ForeignKey(
        "listaEspera.Organizacao",
        on_delete=models.CASCADE,
        related_name="eventos_camp",
        verbose_name="Organização",
    )
    aluno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="eventos_camp",
        verbose_name="Aluno",
    )
    projeto = models.ForeignKey(
        "listaEspera.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos_camp",
        verbose_name="Projeto",
    )
    titulo = models.CharField("Título", max_length=140)
    descricao = models.TextField("Descrição", max_length=500, blank=True)
    tipo = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES, default=TIPO_ATIVIDADE)
    origem = models.CharField(
        "Origem",
        max_length=20,
        choices=ORIGEM_CHOICES,
        default=ORIGEM_ORGANIZACAO,
    )
    data = models.DateField("Data")
    horario = models.TimeField("Horário", null=True, blank=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Evento do calendário"
        verbose_name_plural = "Eventos do calendário"
        ordering = ["data", "horario", "titulo"]
        constraints = [
            models.UniqueConstraint(
                fields=["organizacao", "aluno", "tipo", "titulo", "data"],
                name="unique_evento_calendario",
            )
        ]

    def __str__(self):
        return f"{self.titulo} · {self.data:%d/%m/%Y}"
