from django.apps import AppConfig


class BoardConfig(AppConfig):
    name = 'board'

    def ready(self):
        from . import signals  # noqa: F401
