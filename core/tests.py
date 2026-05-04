"""Tests for the core app: spreadsheet importers and backup command."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from .importers import (
    coerce_date,
    parse_apensos,
    parse_data_nome,
    parse_destino_fazendaria,
    parse_fazendaria_row,
    parse_geral_row,
    parse_numero_processo,
    parse_responsaveis_geral,
    parse_saida_geral,
    parse_situacao_fazendaria,
    parse_situacao_geral,
    parse_tipos_parecer,
)


class ParseTiposParecerTests(SimpleTestCase):
    def test_handles_empty_values(self) -> None:
        self.assertEqual(parse_tipos_parecer(None), [])
        self.assertEqual(parse_tipos_parecer(""), [])
        self.assertEqual(parse_tipos_parecer("   "), [])

    def test_normalizes_full_words(self) -> None:
        self.assertEqual(parse_tipos_parecer("Despacho"), ["D"])
        self.assertEqual(parse_tipos_parecer("despacho"), ["D"])
        self.assertEqual(parse_tipos_parecer("Parecer"), ["P"])
        self.assertEqual(parse_tipos_parecer("Parecer deferindo"), ["Pd"])
        self.assertEqual(parse_tipos_parecer("Parecer indeferindo"), ["Pi"])
        self.assertEqual(parse_tipos_parecer("Remessa"), ["R"])

    def test_accepts_short_codes(self) -> None:
        self.assertEqual(parse_tipos_parecer("D"), ["D"])
        self.assertEqual(parse_tipos_parecer("Pd"), ["Pd"])
        self.assertEqual(parse_tipos_parecer("PD"), ["Pd"])
        self.assertEqual(parse_tipos_parecer("PI"), ["Pi"])
        self.assertEqual(parse_tipos_parecer("R"), ["R"])

    def test_splits_combined_codes(self) -> None:
        self.assertEqual(parse_tipos_parecer("R / Pd"), ["R", "Pd"])
        self.assertEqual(parse_tipos_parecer("R / Pd / D"), ["R", "Pd", "D"])
        self.assertEqual(parse_tipos_parecer("PD;R"), ["Pd", "R"])

    def test_ignores_unknown_tokens(self) -> None:
        self.assertEqual(parse_tipos_parecer("xyz"), [])
        self.assertEqual(parse_tipos_parecer("D / xyz"), ["D"])


class ParseNumeroProcessoTests(SimpleTestCase):
    def test_parses_two_digit_year(self) -> None:
        result = parse_numero_processo("547/25")
        assert result is not None
        self.assertEqual(result.numero, "547/25")
        self.assertEqual(result.ano, 2025)

    def test_parses_four_digit_year(self) -> None:
        result = parse_numero_processo("3712/2025")
        assert result is not None
        self.assertEqual(result.ano, 2025)

    def test_strips_whitespace(self) -> None:
        result = parse_numero_processo(" 6353/21 ")
        assert result is not None
        self.assertEqual(result.numero, "6353/21")
        self.assertEqual(result.ano, 2021)

    def test_returns_none_for_noise(self) -> None:
        self.assertIsNone(parse_numero_processo("apenso"))
        self.assertIsNone(parse_numero_processo("APENSO"))
        self.assertIsNone(parse_numero_processo("   "))
        self.assertIsNone(parse_numero_processo(None))
        self.assertIsNone(parse_numero_processo("II volumes"))


class ParseDataNomeTests(SimpleTestCase):
    def test_parses_date_and_name(self) -> None:
        result = parse_data_nome("05/01/2026 - Dra. Eduarda B")
        assert result is not None
        self.assertEqual(result.data, dt.date(2026, 1, 5))
        self.assertEqual(result.nome, "Dra. Eduarda B")

    def test_parses_two_digit_year(self) -> None:
        result = parse_data_nome("27/01/26 - Dra. Eduarda Barreto")
        assert result is not None
        self.assertEqual(result.data, dt.date(2026, 1, 27))
        self.assertEqual(result.nome, "Dra. Eduarda Barreto")

    def test_handles_only_name(self) -> None:
        result = parse_data_nome("Izabella")
        assert result is not None
        self.assertIsNone(result.data)
        self.assertEqual(result.nome, "Izabella")

    def test_returns_none_for_blank(self) -> None:
        self.assertIsNone(parse_data_nome(""))
        self.assertIsNone(parse_data_nome(None))


class ParseDestinoFazendariaTests(SimpleTestCase):
    def test_parses_setor_and_date(self) -> None:
        result = parse_destino_fazendaria("divativa - 30/03/26")
        assert result is not None
        self.assertEqual(result.setor, "divativa")
        self.assertEqual(result.data, dt.date(2026, 3, 30))

    def test_handles_no_space_around_dash(self) -> None:
        result = parse_destino_fazendaria("Secat-12/01/26")
        assert result is not None
        self.assertEqual(result.setor, "Secat")
        self.assertEqual(result.data, dt.date(2026, 1, 12))

    def test_handles_only_setor(self) -> None:
        result = parse_destino_fazendaria("Gabinete")
        assert result is not None
        self.assertEqual(result.setor, "Gabinete")
        self.assertIsNone(result.data)


class ParseSaidaGeralTests(SimpleTestCase):
    def test_parses_date_then_setor(self) -> None:
        result = parse_saida_geral("06/01/2026 - Procsefop")
        assert result is not None
        self.assertEqual(result.data, dt.date(2026, 1, 6))
        self.assertEqual(result.setor, "Procsefop")

    def test_handles_only_setor(self) -> None:
        result = parse_saida_geral("Segurança Pública")
        assert result is not None
        self.assertEqual(result.setor, "Segurança Pública")
        self.assertIsNone(result.data)


class ParseSituacaoTests(SimpleTestCase):
    def test_fazendaria_situacoes(self) -> None:
        self.assertEqual(parse_situacao_fazendaria("concluído"), "concluido")
        self.assertEqual(parse_situacao_fazendaria("CONCLUÍDO"), "concluido")
        self.assertEqual(parse_situacao_fazendaria("Andamento"), "andamento")
        self.assertEqual(parse_situacao_fazendaria("Remessa"), "remessa")
        self.assertEqual(parse_situacao_fazendaria("no armário"), "no_armario")
        self.assertIsNone(parse_situacao_fazendaria("xyz"))
        self.assertIsNone(parse_situacao_fazendaria(""))

    def test_geral_situacoes(self) -> None:
        self.assertEqual(parse_situacao_geral("ENTREGUE"), "entregue")
        self.assertEqual(parse_situacao_geral("Entregue no caderno"), "caderno")
        self.assertEqual(parse_situacao_geral("ANDAMENTO"), "andamento")
        self.assertEqual(parse_situacao_geral("Análise"), "analise")
        self.assertEqual(parse_situacao_geral("CONCLUÍDO"), "concluido")
        self.assertIsNone(parse_situacao_geral("xyz"))


class ParseApensosTests(SimpleTestCase):
    def test_dash_becomes_empty(self) -> None:
        self.assertEqual(parse_apensos("-"), "")
        self.assertEqual(parse_apensos("--"), "")
        self.assertEqual(parse_apensos(None), "")

    def test_real_value_preserved(self) -> None:
        self.assertEqual(parse_apensos("301/2014"), "301/2014")
        self.assertEqual(parse_apensos(" II volumes "), "II volumes")


class ParseResponsaveisGeralTests(SimpleTestCase):
    def test_single(self) -> None:
        result = parse_responsaveis_geral("Adolpho")
        assert result is not None
        self.assertEqual(result.principal, "Adolpho")
        self.assertIsNone(result.secundario)

    def test_two(self) -> None:
        result = parse_responsaveis_geral("Iely / Rodrigo")
        assert result is not None
        self.assertEqual(result.principal, "Iely")
        self.assertEqual(result.secundario, "Rodrigo")


class CoerceDateTests(SimpleTestCase):
    def test_passthrough_datetime(self) -> None:
        self.assertEqual(
            coerce_date(dt.datetime(2026, 1, 5, 9, 30)), dt.date(2026, 1, 5)
        )

    def test_string_with_date_prefix(self) -> None:
        self.assertEqual(coerce_date("05/01/2026"), dt.date(2026, 1, 5))

    def test_blank_returns_none(self) -> None:
        self.assertIsNone(coerce_date(""))
        self.assertIsNone(coerce_date(None))


class ParseFazendariaRowTests(SimpleTestCase):
    def test_typical_row(self) -> None:
        # 14 columns mirroring the 2026 fazendaria sheet (cols 3, 6-9, 11, 14 are noise).
        row = (
            "547/25", "05/01/2026 - Dra. Eduarda B", None, None, "Lançamento Predial",
            None, None, None, None, "concluído", None, "Secat-12/01/26", "Despacho",
            None,
        )
        record = parse_fazendaria_row(row)
        assert record is not None
        self.assertEqual(record.numero.numero, "547/25")
        self.assertEqual(record.numero.ano, 2025)
        self.assertEqual(record.procurador_nome, "Dra. Eduarda B")
        self.assertEqual(record.data_recebimento, dt.date(2026, 1, 5))
        self.assertEqual(record.assunto, "Lançamento Predial")
        self.assertEqual(record.situacao, "concluido")
        self.assertEqual(record.destino_nome, "Secat")
        self.assertEqual(record.data_remessa, dt.date(2026, 1, 12))
        self.assertEqual(record.tipos_parecer, ["D"])

    def test_apenso_row_returns_none(self) -> None:
        row = ("apenso", None, None, None, None, None, None, None, None,
               None, None, None, None, None)
        self.assertIsNone(parse_fazendaria_row(row))


class ParseGeralRowTests(SimpleTestCase):
    def test_typical_row(self) -> None:
        row = (
            "3712/2025",
            None,
            "-",
            dt.datetime(2026, 1, 5),
            "Procsefop",
            "Retirada de custas",
            "ENTREGUE",
            "06/01/2026 - Procsefop",
            "R",
        )
        record = parse_geral_row(row)
        assert record is not None
        self.assertEqual(record.numero.ano, 2025)
        self.assertIsNone(record.data_entrada)
        self.assertEqual(record.apensos, "")
        self.assertEqual(record.data_distribuicao, dt.date(2026, 1, 5))
        self.assertEqual(record.responsavel_nome, "Procsefop")
        self.assertIsNone(record.responsavel_secundario_nome)
        self.assertEqual(record.assunto, "Retirada de custas")
        self.assertEqual(record.situacao, "entregue")
        self.assertEqual(record.data_saida, dt.date(2026, 1, 6))
        self.assertEqual(record.destino_saida_nome, "Procsefop")
        self.assertEqual(record.tipos_parecer, ["R"])

    def test_co_responsavel_and_apenso(self) -> None:
        row = (
            "2478/2025",
            None,
            "301/2014",
            dt.datetime(2025, 12, 23),
            "Iely / Rodrigo",
            "Autonomia de táxi",
            "ENTREGUE",
            "16/01/2026 - Seg. Pública",
            "R / Pd",
        )
        record = parse_geral_row(row)
        assert record is not None
        self.assertEqual(record.responsavel_nome, "Iely")
        self.assertEqual(record.responsavel_secundario_nome, "Rodrigo")
        self.assertEqual(record.apensos, "301/2014")
        self.assertEqual(record.tipos_parecer, ["R", "Pd"])


def _git_env() -> dict[str, str]:
    """Return env vars that force a deterministic git author/committer.

    This sidesteps any missing ``user.name``/``user.email`` config on the
    machine running the tests.
    """

    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Backup Test",
            "GIT_AUTHOR_EMAIL": "backup-test@example.com",
            "GIT_COMMITTER_NAME": "Backup Test",
            "GIT_COMMITTER_EMAIL": "backup-test@example.com",
        }
    )
    return env


class BackupGitCommandTests(TestCase):
    """End-to-end tests for ``backup_git`` using a local bare repo as remote.

    A bare repository is a real git remote that lives on disk; it lets us push
    without any network access while exercising the full flow (clone, dump,
    copy sqlite, commit, push).
    """

    def setUp(self) -> None:
        # Each test gets a fresh remote so they don't see each other's commits.
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.remote_path = self.tmp_path / "remote.git"
        env = _git_env()
        subprocess.run(
            ["git", "init", "--bare", "-b", "main", str(self.remote_path)],
            check=True,
            capture_output=True,
            env=env,
        )
        seed = self.tmp_path / "seed"
        seed.mkdir()
        for cmd in (
            ["init", "-b", "main"],
            ["commit", "--allow-empty", "-m", "init"],
            ["remote", "add", "origin", str(self.remote_path)],
            ["push", "-u", "origin", "main"],
        ):
            subprocess.run(
                ["git", *cmd],
                cwd=str(seed),
                check=True,
                capture_output=True,
                env=env,
            )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _build_config(self, repo_dir: Path):
        from .management.commands.backup_git import BackupConfig

        return BackupConfig(
            remote=str(self.remote_path),
            branch="main",
            repo_dir=repo_dir,
            db_path=Path(__file__).resolve().parent.parent / "db.sqlite3",
        )

    def _run_with_env(self, repo_dir: Path):
        """Run ``execute_backup`` with deterministic git author env vars."""

        from .management.commands import backup_git as backup_module

        original_run = subprocess.run

        def run_with_env(*args, **kwargs):
            env = kwargs.pop("env", None) or os.environ.copy()
            env.update(_git_env())
            return original_run(*args, env=env, **kwargs)

        config = self._build_config(repo_dir)
        with patch.object(backup_module.subprocess, "run", side_effect=run_with_env):
            return backup_module.execute_backup(config), config

    def test_first_run_clones_and_pushes(self) -> None:
        repo_dir = self.tmp_path / "first_run"
        result, _ = self._run_with_env(repo_dir)
        self.assertTrue(result.committed)
        self.assertTrue(result.pushed)
        self.assertTrue(result.dump_path.exists())
        self.assertEqual(result.dump_path.parent.parent.name, "procuradoria")
        self.assertEqual(result.dump_path.parent.name, "backups")
        # Remote must have received the new commit.
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=str(self.remote_path),
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("backup:", log.stdout)

    def test_second_run_with_no_changes_skips_commit(self) -> None:
        repo_dir = self.tmp_path / "second_run"
        first, _ = self._run_with_env(repo_dir)
        self.assertTrue(first.committed)

        second, _ = self._run_with_env(repo_dir)
        self.assertFalse(
            second.committed,
            "Backup criou commit vazio quando nada mudou.",
        )
        self.assertFalse(second.pushed)


@override_settings(
    BACKUP_GIT_AUTO_ON_PROCESS_CHANGE=True,
    BACKUP_GIT_AUTO_COOLDOWN_SECONDS=0,
)
class ProcessAutoBackupSignalTests(TestCase):
    """Signal tests for automatic backup on process CRUD changes."""

    def test_runs_backup_on_process_create_update_delete(self) -> None:
        from geral.models import ProcessoGeral

        with patch("core.process_backup_signals.call_command") as mocked_call:
            process = ProcessoGeral.objects.create(numero_processo="9001/26", ano=2026)
            process.observacoes = "Atualizado por teste"
            process.save(update_fields=["observacoes"])
            process.delete()

        self.assertEqual(mocked_call.call_count, 3)
        mocked_call.assert_called_with("backup_git")

    def test_respects_cooldown_window(self) -> None:
        from geral.models import ProcessoGeral

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_file = Path(tmp_dir) / "last_run.txt"
            state_file.write_text(str(time.time()), encoding="utf-8")
            with override_settings(
                BACKUP_GIT_AUTO_ON_PROCESS_CHANGE=True,
                BACKUP_GIT_AUTO_COOLDOWN_SECONDS=120,
                BACKUP_GIT_AUTO_COOLDOWN_STATE_FILE=state_file,
            ):
                with patch("core.process_backup_signals.call_command") as mocked_call:
                    ProcessoGeral.objects.create(numero_processo="9003/26", ano=2026)

        mocked_call.assert_not_called()

    def test_updates_cooldown_state_file_after_success(self) -> None:
        from geral.models import ProcessoGeral

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_file = Path(tmp_dir) / "last_run.txt"
            state_file.write_text("1.0", encoding="utf-8")
            with override_settings(
                BACKUP_GIT_AUTO_ON_PROCESS_CHANGE=True,
                BACKUP_GIT_AUTO_COOLDOWN_SECONDS=120,
                BACKUP_GIT_AUTO_COOLDOWN_STATE_FILE=state_file,
            ):
                with patch("core.process_backup_signals.call_command") as mocked_call:
                    with patch(
                        "core.process_backup_signals.time.time",
                        side_effect=[1000.0, 1000.0],
                    ):
                        ProcessoGeral.objects.create(numero_processo="9004/26", ano=2026)
                mocked_call.assert_called_once_with("backup_git")
                self.assertEqual(state_file.read_text(encoding="utf-8").strip(), "1000.0")


@override_settings(BACKUP_GIT_AUTO_ON_PROCESS_CHANGE=False)
class ProcessAutoBackupDisabledTests(TestCase):
    def test_does_not_run_backup_when_flag_is_disabled(self) -> None:
        from geral.models import ProcessoGeral

        with patch("core.process_backup_signals.call_command") as mocked_call:
            ProcessoGeral.objects.create(numero_processo="9002/26", ano=2026)

        mocked_call.assert_not_called()


class CoreServiceReportTests(TestCase):
    """Tests for the rich dashboard / relatorio service helpers."""

    @classmethod
    def setUpTestData(cls) -> None:
        from core.models import Assunto, Modulo, Procurador, Setor, TipoParecer
        from fazendaria.models import ProcessoFazendaria, SituacaoFazendaria
        from geral.models import ProcessoGeral, SituacaoGeral

        cls.proc = Procurador.objects.create(
            nome="Dra. Eduarda", modulo=Modulo.AMBOS
        )
        cls.setor = Setor.objects.create(nome="DIVATIVA")
        cls.assunto_faz = Assunto.objects.create(
            nome="Lançamento", modulo=Modulo.FAZENDARIA
        )
        cls.assunto_geral = Assunto.objects.create(
            nome="Permuta", modulo=Modulo.GERAL
        )
        cls.tp = TipoParecer.objects.create(codigo="P", nome="Parecer")

        today = dt.date.today()
        cls.faz = ProcessoFazendaria.objects.create(
            numero_processo="100/26",
            ano=today.year,
            procurador=cls.proc,
            data_recebimento=today,
            assunto=cls.assunto_faz,
            destino=cls.setor,
            situacao=SituacaoFazendaria.ANDAMENTO,
        )
        cls.faz.tipos_parecer.add(cls.tp)

        cls.ger = ProcessoGeral.objects.create(
            numero_processo="200/2026",
            ano=today.year,
            data_distribuicao=today,
            responsavel=cls.proc,
            assunto=cls.assunto_geral,
            destino_saida=cls.setor,
            situacao=SituacaoGeral.ANDAMENTO,
        )
        cls.ger.tipos_parecer.add(cls.tp)

    def test_dashboard_summaries_include_both_modules(self) -> None:
        from core.services import get_dashboard_summaries

        summaries = get_dashboard_summaries()
        slugs = {s.slug for s in summaries}
        self.assertEqual(slugs, {"fazendaria", "geral"})
        for s in summaries:
            self.assertGreaterEqual(s.total, 1)

    def test_recent_processes_returns_items_from_both_modules(self) -> None:
        from core.services import get_recent_processes

        recent = get_recent_processes(limit=5)
        modulos = {item.modulo for item in recent}
        self.assertEqual(modulos, {"Fazendária", "Geral"})

    def test_fazendaria_report_has_top_lists_and_monthly(self) -> None:
        from core.services import fazendaria_report

        report = fazendaria_report()
        self.assertIsNotNone(report)
        assert report is not None
        self.assertEqual(report.total, 1)
        self.assertEqual(len(report.monthly), 12)
        self.assertEqual(report.monthly_max, 1)
        self.assertEqual(report.top_procuradores[0].count, 1)
        self.assertEqual(report.top_setores[0].count, 1)
        self.assertEqual(report.top_pareceres[0].count, 1)
        labels = [c.label for c in report.counters]
        self.assertIn("Em andamento", labels)

    def test_geral_report_has_top_lists_and_monthly(self) -> None:
        from core.services import geral_report

        report = geral_report()
        self.assertIsNotNone(report)
        assert report is not None
        self.assertEqual(report.total, 1)
        self.assertEqual(len(report.monthly), 12)
        self.assertGreaterEqual(report.monthly_max, 1)
        self.assertEqual(report.top_procuradores[0].count, 1)

    def test_global_search_finds_in_both_modules(self) -> None:
        from core.services import global_search

        hits = global_search("100/26")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].modulo, "Fazendária")

        hits = global_search("200")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].modulo, "Geral")

        self.assertEqual(global_search(""), [])


class CoreSearchViewTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        from django.contrib.auth import get_user_model
        from core.models import Assunto, Modulo
        from fazendaria.models import ProcessoFazendaria, SituacaoFazendaria

        cls.user = get_user_model().objects.create_user(username="u", password="x")
        cls.assunto = Assunto.objects.create(nome="X", modulo=Modulo.FAZENDARIA)
        ProcessoFazendaria.objects.create(
            numero_processo="ABC123/26",
            ano=2026,
            assunto=cls.assunto,
            situacao=SituacaoFazendaria.ANDAMENTO,
        )

    def setUp(self) -> None:
        self.client.login(username="u", password="x")

    def test_search_view_renders_results(self) -> None:
        from django.urls import reverse

        resp = self.client.get(reverse("core:busca"), {"q": "ABC123"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "ABC123/26")

    def test_search_view_without_query_renders_empty(self) -> None:
        from django.urls import reverse

        resp = self.client.get(reverse("core:busca"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "ABC123/26")
