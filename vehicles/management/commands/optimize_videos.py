"""
Re-encode existing uploaded videos for smooth mobile streaming.

New uploads are optimized automatically in the background; run this once for
videos uploaded before that, or to retry a failed/interrupted optimization.

    python manage.py optimize_videos --dry-run
    python manage.py optimize_videos
    python manage.py optimize_videos --model vehicles.dealervehiclereel
"""

from django.core.management.base import BaseCommand, CommandError

from vehicles.video_processing import (
    _get_model_video_field_name,
    ffmpeg_available,
    needs_optimization,
    optimize_video,
    video_models,
)


class Command(BaseCommand):
    help = "Re-encode uploaded videos (720p H.264, faststart) for smooth mobile streaming."

    def add_arguments(self, parser):
        parser.add_argument('--model', help="Only this model, e.g. vehicles.dealervehiclereel")
        parser.add_argument('--dry-run', action='store_true', help="List videos that would be optimized")

    def handle(self, *args, **options):
        if not options['dry_run'] and not ffmpeg_available():
            raise CommandError("ffmpeg/ffprobe are not installed in this environment.")

        models = video_models()
        if options['model']:
            models = [m for m in models if m._meta.label_lower == options['model'].lower()]
            if not models:
                raise CommandError(f"No video model found named {options['model']}")

        for model in models:
            field_name = _get_model_video_field_name(model)
            rows = model.objects.exclude(**{field_name: ''}).exclude(**{f'{field_name}__isnull': True})
            for pk, name in rows.values_list('pk', field_name):
                if not needs_optimization(name):
                    continue
                label = f"{model._meta.label} #{pk}: {name}"
                if options['dry_run']:
                    self.stdout.write(f"Would optimize {label}")
                    continue
                self.stdout.write(f"Optimizing {label} ...")
                try:
                    new_name = optimize_video(model, pk, name, field_name=field_name)
                except Exception as exc:
                    self.stderr.write(self.style.ERROR(f"  failed: {exc}"))
                    continue
                if new_name:
                    self.stdout.write(self.style.SUCCESS(f"  -> {new_name}"))
                else:
                    self.stdout.write("  skipped")
