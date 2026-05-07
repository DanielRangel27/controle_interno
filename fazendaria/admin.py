"""Admin registration for the fazendaria module."""

from __future__ import annotations

from django.contrib import admin

from .models import ProcessoFazendaria


@admin.register(ProcessoFazendaria)
class ProcessoFazendariaAdmin(admin.ModelAdmin):
    list_display = (
        "numero_processo",
        "ano",
        "procurador",
        "data_recebimento",
        "assunto",
        "situacao",
        "destino",
        "data_remessa",
    )
    list_filter = ("ano", "situacao", "procurador", "destino")
    search_fields = ("numero_processo", "observacoes", "apensos")
    autocomplete_fields = ("procurador", "assunto", "destino")
    filter_horizontal = ("tipos_parecer",)
    date_hierarchy = "data_recebimento"
    ordering = ("-ano", "-data_recebimento")
