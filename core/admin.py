"""Admin registrations for shared catalog models."""

from __future__ import annotations

from django.contrib import admin

from .models import Assunto, Procurador, Setor, TipoParecer


@admin.register(Procurador)
class ProcuradorAdmin(admin.ModelAdmin):
    list_display = ("nome", "modulo", "ativo", "atualizado_em")
    list_filter = ("modulo", "ativo")
    search_fields = ("nome",)
    list_editable = ("ativo",)
    ordering = ("nome",)


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla", "ativo", "atualizado_em")
    list_filter = ("ativo",)
    search_fields = ("nome", "sigla")
    list_editable = ("ativo",)
    ordering = ("nome",)


@admin.register(Assunto)
class AssuntoAdmin(admin.ModelAdmin):
    list_display = ("nome", "modulo", "ativo", "atualizado_em")
    list_filter = ("modulo", "ativo")
    search_fields = ("nome",)
    list_editable = ("ativo",)
    ordering = ("nome",)


@admin.register(TipoParecer)
class TipoParecerAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "ativo")
    list_filter = ("ativo",)
    search_fields = ("codigo", "nome")
    list_editable = ("ativo",)
    ordering = ("nome",)
