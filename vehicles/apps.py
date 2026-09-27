from django.apps import AppConfig


class VehiclesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vehicles'

    def ready(self):
        from .video_processing import connect_signals
        connect_signals()

