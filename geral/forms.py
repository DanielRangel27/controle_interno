"""Forms for the geral module."""

from __future__ import annotations

from django import forms

from core.models import Assunto, Modulo, Procurador, Setor, TipoParecer

from .models import ProcessoGeral, SituacaoGeral


class ProcessoGeralForm(forms.ModelForm):
    class Meta:
        model = ProcessoGeral
        fields = [
            "numero_processo",
            "ano",
            "data_entrada",
            "apensos",
            "data_distribuicao",
            "responsavel",
            "responsavel_secundario",
            "assunto",
            "observacoes",
            "situacao",
            "data_saida",
            "destino_saida",
            "tipos_parecer",
        ]
        widgets = {
            "data_entrada": forms.DateInput(attrs={"type": "date"}),
            "data_distribuicao": forms.DateInput(attrs={"type": "date"}),
            "data_saida": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
            "tipos_parecer": forms.CheckboxSelectMultiple,
            "apensos": forms.TextInput(
                attrs={"placeholder": "Ex.: 1405/2023 ou deixe em branco"}
            ),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        responsavel_qs = Procurador.objects.filter(
            ativo=True, modulo__in=[Modulo.GERAL, Modulo.AMBOS]
        )
        self.fields["responsavel"].queryset = responsavel_qs
        self.fields["responsavel_secundario"].queryset = responsavel_qs
        self.fields["assunto"].queryset = Assunto.objects.filter(
            ativo=True, modulo__in=[Modulo.GERAL, Modulo.AMBOS]
        )
        self.fields["destino_saida"].queryset = Setor.objects.filter(ativo=True)
        self.fields["tipos_parecer"].queryset = TipoParecer.objects.filter(ativo=True)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " form-control").strip()

    def clean(self) -> dict:
        cleaned = super().clean()
        responsavel = cleaned.get("responsavel")
        secundario = cleaned.get("responsavel_secundario")
        if responsavel and secundario and responsavel == secundario:
            self.add_error(
                "responsavel_secundario",
                "O co-responsável deve ser diferente do responsável principal.",
            )
        return cleaned


class FiltroProcessoForm(forms.Form):
    busca = forms.CharField(
        label="Busca",
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "Número, observação ou apenso"}
        ),
    )
    ano = forms.IntegerField(label="Ano", required=False, min_value=2000, max_value=2100)
    situacao = forms.ChoiceField(
        label="Situação",
        required=False,
        choices=[("", "Todas")] + list(SituacaoGeral.choices),
    )
    responsavel = forms.ModelChoiceField(
        label="Responsável",
        required=False,
        queryset=Procurador.objects.none(),
        empty_label="Todos",
    )
    destino = forms.ModelChoiceField(
        label="Destino",
        required=False,
        queryset=Setor.objects.none(),
        empty_label="Todos",
    )
    assunto = forms.ModelChoiceField(
        label="Assunto",
        required=False,
        queryset=Assunto.objects.none(),
        empty_label="Todos",
    )
    tipo_parecer = forms.ModelChoiceField(
        label="Parecer",
        required=False,
        queryset=TipoParecer.objects.none(),
        empty_label="Todos",
    )
    data_inicio = forms.DateField(
        label="Distribuído a partir de",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    data_fim = forms.DateField(
        label="Distribuído até",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["responsavel"].queryset = Procurador.objects.filter(
            ativo=True, modulo__in=[Modulo.GERAL, Modulo.AMBOS]
        )
        self.fields["destino"].queryset = Setor.objects.filter(ativo=True)
        self.fields["assunto"].queryset = Assunto.objects.filter(
            ativo=True, modulo__in=[Modulo.GERAL, Modulo.AMBOS]
        )
        self.fields["tipo_parecer"].queryset = TipoParecer.objects.filter(ativo=True)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " form-control").strip()
