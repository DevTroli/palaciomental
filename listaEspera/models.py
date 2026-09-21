from django.db import models


class WaitlistEntry(models.Model):
    """Entrada na lista de espera do Palácio Mental."""
    nome = models.CharField("Nome", max_length=120)
    telefone = models.CharField("Telefone", max_length=20)
    email = models.EmailField("E-mail")
    consent = models.BooleanField("Consentimento LGPD", default=False)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Entrada na Lista de Espera"
        verbose_name_plural = "Entradas na Lista de Espera"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.nome} ({self.email})"
