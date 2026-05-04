"""Forms for the accounts module (public signup with admin approval)."""

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class SignupForm(UserCreationForm):
    """Public signup form: collects username, optional email, name and password.

    The created user is intentionally returned with ``is_active=False``; the
    actual deactivation is enforced by the view to keep the form reusable.
    """

    first_name = forms.CharField(
        label="Nome",
        max_length=150,
        required=False,
    )
    last_name = forms.CharField(
        label="Sobrenome",
        max_length=150,
        required=False,
    )
    email = forms.EmailField(
        label="E-mail",
        required=True,
        help_text="Usado para contato pela administração.",
    )

    class Meta:
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email")

    def clean_email(self) -> str:
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            return email
        user_model = get_user_model()
        if user_model.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe um usuário com este e-mail.")
        return email
