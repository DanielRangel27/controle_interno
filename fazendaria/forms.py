"""Forms for the fazendaria module."""

from __future__ import annotations

from django import forms

from core.models import Assunto, Modulo, Procurador, Setor, TipoParecer

from .models import ProcessoFazendaria, SituacaoFazendaria


class ProcessoFazendariaForm(forms.ModelForm):
    """Form for creating/editing a fazendaria process.

    Limits the dropdowns to active records assigned to fazendaria/ambos.
    """

    class Meta:
        model = ProcessoFazendaria
        fields = [
            "numero_processo",
            "ano",
            "procurador",
            "data_recebimento",
            "assunto",
            "observacoes",
            "situacao",
            "destino",
            "data_remessa",
            "tipos_parecer",
        ]
        widgets = {
            "data_recebimento": forms.DateInput(attrs={"type": "date"}),
            "data_remessa": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
            "tipos_parecer": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["procurador"].queryset = Procurador.objects.filter(
            ativo=True, modulo__in=[Modulo.FAZENDARIA, Modulo.AMBOS]
        )
        self.fields["assunto"].queryset = Assunto.objects.filter(
            ativo=True, modulo__in=[Modulo.FAZENDARIA, Modulo.AMBOS]
        )
        self.fields["destino"].queryset = Setor.objects.filter(ativo=True)
        self.fields["tipos_parecer"].queryset = TipoParecer.objects.filter(ativo=True)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxSelectMultiple):
                continue
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = (existing + " form-control").strip()


class FiltroProcessoForm(forms.Form):
    """Filter form rendered above the listing."""

    busca = forms.CharField(
        label="Busca",
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "Número do processo ou observação"}
        ),
    )
    ano = forms.IntegerField(label="Ano", required=False, min_value=2000, max_value=2100)
    situacao = forms.ChoiceField(
        label="Situação",
        required=False,
        choices=[("", "Todas")] + list(SituacaoFazendaria.choices),
    )
    procurador = forms.ModelChoiceField(
        label="Procurador",
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
        label="Recebido a partir de",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    data_fim = forms.DateField(
        label="Recebido até",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["procurador"].queryset = Procurador.objects.filter(
            ativo=True, modulo__in=[Modulo.FAZENDARIA, Modulo.AMBOS]
        )
        self.fields["destino"].queryset = Setor.objects.filter(ativo=True)
        self.fields["assunto"].queryset = Assunto.objects.filter(
            ativo=True, modulo__in=[Modulo.FAZENDARIA, Modulo.AMBOS]
        )
        self.fields["tipo_parecer"].queryset = TipoParecer.objects.filter(ativo=True)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " form-control").strip()
