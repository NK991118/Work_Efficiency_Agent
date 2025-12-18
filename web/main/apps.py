from django.apps import AppConfig

class MainConfig(AppConfig):
    name = "main"

    def ready(self):
        from .views import embedding_fn
        embedding_fn.model()
