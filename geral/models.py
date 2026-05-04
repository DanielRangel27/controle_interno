"""Models for the Geral prosecution module.

Mirrors the 2026 tab of ``001 - Controle Interno de Processos copia.xlsm``,
which uses the new (clean) layout with 9 columns:

    PROCESSO | DATA | APENSOS | DISTRIBUIDO | RESPONSAVEL | ASSUNTO |
    SITUACAO | SAIDA | Arquivado/Despacho/Parecer/Remessa
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import Assunto, Procurador, Setor, TimestampedModel, TipoParecer


class SituacaoGeral(models.TextChoices):
    """Real values observed in the 2026 sheet of the geral spreadsheet."""

    ENTREGUE = "entregue", "Entregue"
    ANDAMENTO = "andamento", "Em andamento"
    CADERNO = "caderno", "Entregue no caderno"
    ANALISE = "analise", "Em análise"
    CONCLUIDO = "concluido", "Concluído"


class ProcessoGeral(TimestampedModel):
    numero_processo = models.CharField("número do processo", max_length=32)
    ano = models.PositiveSmallIntegerField("ano")

    data_entrada = models.DateField("data de entrada", null=True, blank=True)
    apensos = models.CharField("apensos", max_length=120, blank=True)
    data_distribuicao = models.DateField("data de distribuição", null=True, blank=True)

    responsavel = models.ForeignKey(
        Procurador,
        verbose_name="responsável",
        on_delete=models.PROTECT,
        related_name="processos_geral",
        null=True,
        blank=True,
    )
    responsavel_secundario = models.ForeignKey(
        Procurador,
        verbose_name="co-responsável",
        on_delete=models.PROTECT,
        related_name="processos_geral_secundario",
        null=True,
        blank=True,
        help_text="Usado quando o processo é dividido entre dois procuradores.",
    )

    assunto = models.ForeignKey(
        Assunto,
        verbose_name="assunto",
        on_delete=models.PROTECT,
        related_name="processos_geral",
        null=True,
        blank=True,
    )
    observacoes = models.TextField("observações", blank=True)

    situacao = models.CharField(
        "situação",
        max_length=20,
        choices=SituacaoGeral.choices,
        default=SituacaoGeral.ANDAMENTO,
    )

    data_saida = models.DateField("data de saída", null=True, blank=True)
    destino_saida = models.ForeignKey(
        Setor,
        verbose_name="destino da saída",
        on_delete=models.PROTECT,
        related_name="processos_geral",
        null=True,
        blank=True,
    )

    tipos_parecer = models.ManyToManyField(
        TipoParecer,
        verbose_name="tipos de parecer",
        related_name="processos_geral",
        blank=True,
    )

    importado = models.BooleanField("importado da planilha", default=False)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processos_geral_criados",
    )

    class Meta:
        ordering = ["-ano", "-data_entrada", "-criado_em"]
        unique_together = [("numero_processo", "ano")]
        verbose_name = "processo (geral)"
        verbose_name_plural = "processos (geral)"
        indexes = [
            models.Index(fields=["ano"]),
            models.Index(fields=["situacao"]),
            models.Index(fields=["responsavel"]),
            models.Index(fields=["destino_saida"]),
        ]

    def __str__(self) -> str:
        return f"{self.numero_processo} ({self.ano})"
