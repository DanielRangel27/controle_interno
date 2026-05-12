"""Forms for the geral module."""

from __future__ import annotations

from django import forms

from core.models import Assunto, Modulo, Procurador, Setor, TipoParecer

from .models import ProcessoGeral, SituacaoGeral


class ProcessoGeralForm(forms.ModelForm):
    assunto_nome = forms.CharField(label="Assunto", required=False, max_length=200)
    destino_saida_nome = forms.CharField(
        label="Destino da saída",
        required=False,
        max_length=120,
    )

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
            "data_entrada": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "data_distribuicao": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "data_saida": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
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
        self.fields["tipos_parecer"].queryset = TipoParecer.objects.filter(ativo=True)
        if not self.instance.pk and not self.is_bound:
            self.initial.setdefault("situacao", SituacaoGeral.DISTRIBUICAO)
        if self.instance.pk:
            if self.instance.assunto:
                self.initial["assunto_nome"] = self.instance.assunto.nome
            if self.instance.destino_saida:
                self.initial["destino_saida_nome"] = self.instance.destino_saida.nome
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " form-control").strip()

    def clean(self) -> dict:
        cleaned = super().clean()
        assunto_nome = (cleaned.get("assunto_nome") or "").strip()
        destino_saida_nome = (cleaned.get("destino_saida_nome") or "").strip()
        cleaned["assunto_nome"] = assunto_nome
        cleaned["destino_saida_nome"] = destino_saida_nome
        cleaned["assunto"] = self._resolve_assunto(assunto_nome)
        cleaned["destino_saida"] = self._resolve_destino_saida(destino_saida_nome)

        responsavel = cleaned.get("responsavel")
        secundario = cleaned.get("responsavel_secundario")
        if responsavel and secundario and responsavel == secundario:
            self.add_error(
                "responsavel_secundario",
                "O co-responsável deve ser diferente do responsável principal.",
            )
        return cleaned

    def _resolve_assunto(self, nome: str) -> Assunto | None:
        if not nome:
            return None
        existing = Assunto.objects.filter(nome__iexact=nome, modulo=Modulo.GERAL).first()
        if existing:
            return existing
        existing_ambos = Assunto.objects.filter(
            nome__iexact=nome,
            modulo=Modulo.AMBOS,
        ).first()
        if existing_ambos:
            return existing_ambos
        return Assunto.objects.create(nome=nome, modulo=Modulo.GERAL, ativo=True)

    def _resolve_destino_saida(self, nome: str) -> Setor | None:
        if not nome:
            return None
        existing = Setor.objects.filter(nome__iexact=nome).first()
        if existing:
            return existing
        return Setor.objects.create(nome=nome, ativo=True)


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
        label="Distribuído a partir de",
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    data_fim = forms.DateField(
        label="Distribuído até",
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["responsavel"].queryset = Procurador.objects.filter(
            ativo=True, modulo__in=[Modulo.GERAL, Modulo.AMBOS]
        )
        self.fields["tipo_parecer"].queryset = TipoParecer.objects.filter(ativo=True)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " form-control").strip()
