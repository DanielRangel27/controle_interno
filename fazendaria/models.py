"""Models for the Fazendaria (PROCSEFOP) prosecution module.

The fields below mirror the 2026 tab of
``CONTROLE DE PA - PROCSEFOP 2021-22 (Recuperado) - Copia.xlsx``.
After resolving merged cells, that tab has 6 logical columns:

    1. N PROCESSO                      -> numero_processo + ano
    2. PROCURADOR Outros / Data Rec.   -> procurador + data_recebimento
    3. ASSUNTO / Observacoes           -> assunto + observacoes
    4. SITUACAO                        -> situacao
    5. Destino / Data Remessa          -> destino + data_remessa
    6. Parecer / Despacho / Remessa    -> tipos_parecer (M2M)
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import Assunto, Procurador, Setor, TimestampedModel, TipoParecer


class SituacaoFazendaria(models.TextChoices):
    """Real values observed in the 2026 sheet of the fazendaria spreadsheet."""

    ANDAMENTO = "andamento", "Em andamento"
    CONCLUIDO = "concluido", "Concluído"
    REMESSA = "remessa", "Remessa"
    NO_ARMARIO = "no_armario", "No armário"
    DISTRIBUICAO = "distribuicao", "Distribuição"
    ARQUIVADO = "arquivado", "Arquivado"
    ENTREGUE = "entregue", "Entregue"
    DIARIO_OFICIAL = "diario_oficial", "Diário Oficial"


class ProcessoFazendaria(TimestampedModel):
    numero_processo = models.CharField("número do processo", max_length=32)
    ano = models.PositiveSmallIntegerField("ano")

    procurador = models.ForeignKey(
        Procurador,
        verbose_name="procurador",
        on_delete=models.PROTECT,
        related_name="processos_fazendaria",
        null=True,
        blank=True,
    )
    data_recebimento = models.DateField("data de recebimento", null=True, blank=True)
    data_distribuicao = models.DateField("data de distribuição", null=True, blank=True)

    assunto = models.ForeignKey(
        Assunto,
        verbose_name="assunto",
        on_delete=models.PROTECT,
        related_name="processos_fazendaria",
        null=True,
        blank=True,
    )
    observacoes = models.TextField("observações", blank=True)

    situacao = models.CharField(
        "situação",
        max_length=20,
        choices=SituacaoFazendaria.choices,
        default=SituacaoFazendaria.ANDAMENTO,
    )

    destino = models.ForeignKey(
        Setor,
        verbose_name="destino",
        on_delete=models.PROTECT,
        related_name="processos_fazendaria",
        null=True,
        blank=True,
    )
    data_remessa = models.DateField("data da remessa", null=True, blank=True)

    tipos_parecer = models.ManyToManyField(
        TipoParecer,
        verbose_name="tipos de parecer",
        related_name="processos_fazendaria",
        blank=True,
    )

    importado = models.BooleanField("importado da planilha", default=False)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processos_fazendaria_criados",
    )

    class Meta:
        ordering = ["-ano", "-data_recebimento", "-criado_em"]
        unique_together = [("numero_processo", "ano")]
        verbose_name = "processo (fazendária)"
        verbose_name_plural = "processos (fazendária)"
        indexes = [
            models.Index(fields=["ano"]),
            models.Index(fields=["situacao"]),
            models.Index(fields=["procurador"]),
            models.Index(fields=["destino"]),
        ]

    def __str__(self) -> str:
        return f"{self.numero_processo} ({self.ano})"

    @property
    def numero_completo(self) -> str:
        return f"{self.numero_processo}/{str(self.ano)[-2:]}"
