"""Admin registration for the geral module."""

from __future__ import annotations

from django.contrib import admin

from .models import ProcessoGeral


@admin.register(ProcessoGeral)
class ProcessoGeralAdmin(admin.ModelAdmin):
    list_display = (
        "numero_processo",
        "ano",
        "data_entrada",
        "data_distribuicao",
        "responsavel",
        "assunto",
        "situacao",
        "destino_saida",
        "data_saida",
    )
    list_filter = ("ano", "situacao", "responsavel", "destino_saida")
    search_fields = ("numero_processo", "observacoes", "apensos")
    autocomplete_fields = (
        "responsavel",
        "responsavel_secundario",
        "assunto",
        "destino_saida",
    )
    filter_horizontal = ("tipos_parecer",)
    date_hierarchy = "data_entrada"
    ordering = ("-ano", "-data_entrada")
