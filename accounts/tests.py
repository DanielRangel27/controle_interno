"""Tests for the accounts (signup with admin approval) module."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class SignupViewTests(TestCase):
    """Public signup creates an inactive user pending admin approval."""

    def test_get_signup_page(self) -> None:
        response = self.client.get(reverse("accounts:signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Solicitar acesso")

    def test_signup_creates_inactive_user(self) -> None:
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "joao",
                "first_name": "João",
                "last_name": "Silva",
                "email": "joao@example.com",
                "password1": "Senha-muito-forte-123",
                "password2": "Senha-muito-forte-123",
            },
        )
        self.assertRedirects(response, reverse("accounts:signup_pendente"))
        user = User.objects.get(username="joao")
        self.assertFalse(user.is_active, "Novo usuário deveria nascer inativo.")
        self.assertEqual(user.email, "joao@example.com")

    def test_signup_rejects_duplicate_email(self) -> None:
        User.objects.create_user(
            username="existente",
            email="existe@example.com",
            password="x",
        )
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "outro",
                "email": "Existe@example.com",
                "password1": "Senha-muito-forte-123",
                "password2": "Senha-muito-forte-123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Já existe um usuário com este e-mail.")
        self.assertFalse(User.objects.filter(username="outro").exists())


class InactiveUserCannotLoginTests(TestCase):
    def test_inactive_user_login_is_rejected(self) -> None:
        user = User.objects.create_user(
            username="pendente",
            password="Senha-muito-forte-123",
            email="p@example.com",
        )
        user.is_active = False
        user.save()

        ok = self.client.login(username="pendente", password="Senha-muito-forte-123")
        self.assertFalse(ok, "Usuário inativo não pode autenticar.")
