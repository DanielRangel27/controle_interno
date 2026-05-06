"""Forms for the fazendaria module."""

from __future__ import annotations

from django import forms

from core.models import Assunto, Modulo, Procurador, Setor, TipoParecer

from .models import ProcessoFazendaria, SituacaoFazendaria


class ProcessoFazendariaForm(forms.ModelForm):
    """Form for creating/editing a fazendaria process.

    Limits the dropdowns to active records assigned to fazendaria/ambos.
    """

    assunto_nome = forms.CharField(label="Assunto", required=False, max_length=200)
    destino_nome = forms.CharField(label="Destino", required=False, max_length=120)

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
            "data_recebimento": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "data_remessa": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
            "tipos_parecer": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["procurador"].queryset = Procurador.objects.filter(
            ativo=True, modulo__in=[Modulo.FAZENDARIA, Modulo.AMBOS]
        )
        self.fields["tipos_parecer"].queryset = TipoParecer.objects.filter(ativo=True)
        if self.instance.pk:
            if self.instance.assunto:
                self.initial["assunto_nome"] = self.instance.assunto.nome
            if self.instance.destino:
                self.initial["destino_nome"] = self.instance.destino.nome
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxSelectMultiple):
                continue
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = (existing + " form-control").strip()

    def clean(self) -> dict:
        cleaned = super().clean()
        assunto_nome = (cleaned.get("assunto_nome") or "").strip()
        destino_nome = (cleaned.get("destino_nome") or "").strip()
        cleaned["assunto_nome"] = assunto_nome
        cleaned["destino_nome"] = destino_nome
        cleaned["assunto"] = self._resolve_assunto(assunto_nome)
        cleaned["destino"] = self._resolve_destino(destino_nome)
        return cleaned

    def _resolve_assunto(self, nome: str) -> Assunto | None:
        if not nome:
            return None
        existing = Assunto.objects.filter(
            nome__iexact=nome, modulo=Modulo.FAZENDARIA
        ).first()
        if existing:
            return existing
        existing_ambos = Assunto.objects.filter(
            nome__iexact=nome,
            modulo=Modulo.AMBOS,
        ).first()
        if existing_ambos:
            return existing_ambos
        return Assunto.objects.create(nome=nome, modulo=Modulo.FAZENDARIA, ativo=True)

    def _resolve_destino(self, nome: str) -> Setor | None:
        if not nome:
            return None
        existing = Setor.objects.filter(nome__iexact=nome).first()
        if existing:
            return existing
        return Setor.objects.create(nome=nome, ativo=True)


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
    destino = forms.CharField(
        label="Destino",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Digite o destino"}),
    )
    assunto = forms.CharField(
        label="Assunto",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Digite o assunto"}),
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
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    data_fim = forms.DateField(
        label="Recebido até",
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["procurador"].queryset = Procurador.objects.filter(
            ativo=True, modulo__in=[Modulo.FAZENDARIA, Modulo.AMBOS]
        )
        self.fields["tipo_parecer"].queryset = TipoParecer.objects.filter(ativo=True)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " form-control").strip()
