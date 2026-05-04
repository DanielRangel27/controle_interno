"""Shared catalog models used by both fazendaria and geral modules."""

from __future__ import annotations

from django.db import models


class Modulo(models.TextChoices):
    """Identifies which prosecution office a record belongs to."""

    FAZENDARIA = "fazendaria", "Fazendária"
    GERAL = "geral", "Geral"
    AMBOS = "ambos", "Ambos"


class TimestampedModel(models.Model):
    """Abstract base providing creation/update timestamps."""

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Procurador(TimestampedModel):
    nome = models.CharField("nome", max_length=120, unique=True)
    modulo = models.CharField(
        "módulo",
        max_length=16,
        choices=Modulo.choices,
        default=Modulo.AMBOS,
    )
    ativo = models.BooleanField("ativo", default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "procurador"
        verbose_name_plural = "procuradores"

    def __str__(self) -> str:
        return self.nome


class Setor(TimestampedModel):
    """Destination sector / public agency that receives processes."""

    nome = models.CharField("nome", max_length=120, unique=True)
    sigla = models.CharField("sigla", max_length=32, blank=True)
    ativo = models.BooleanField("ativo", default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "setor"
        verbose_name_plural = "setores"

    def __str__(self) -> str:
        if self.sigla:
            return f"{self.sigla} - {self.nome}"
        return self.nome


class Assunto(TimestampedModel):
    nome = models.CharField("nome", max_length=200)
    modulo = models.CharField(
        "módulo",
        max_length=16,
        choices=Modulo.choices,
        default=Modulo.AMBOS,
    )
    ativo = models.BooleanField("ativo", default=True)

    class Meta:
        ordering = ["nome"]
        unique_together = [("nome", "modulo")]
        verbose_name = "assunto"
        verbose_name_plural = "assuntos"

    def __str__(self) -> str:
        return self.nome


class TipoParecer(TimestampedModel):
    """Normalized parecer types observed in the spreadsheets.

    Examples from the 2026 sheets:
        - D  -> Despacho
        - P  -> Parecer
        - Pd -> Parecer deferindo
        - Pi -> Parecer indeferindo
        - R  -> Remessa
    """

    codigo = models.CharField("código", max_length=8, unique=True)
    nome = models.CharField("nome", max_length=80)
    ativo = models.BooleanField("ativo", default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "tipo de parecer"
        verbose_name_plural = "tipos de parecer"

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nome}"
