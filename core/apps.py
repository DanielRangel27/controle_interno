from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self) -> None:
        from . import process_backup_signals

        process_backup_signals.connect_process_backup_signals()
