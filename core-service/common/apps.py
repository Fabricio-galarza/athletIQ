from django.apps import AppConfig

class CommonConfig(AppConfig):
    name = 'core.common'

    def ready(self):
        import core.common.signals