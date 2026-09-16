import os
from django.core.management.base import BaseCommand
from django.conf import settings
from vehicles.models import Music

class Command(BaseCommand):
    help = 'Seeds initial background music tracks from media/music into the database.'

    DEFAULT_TRACKS = [
        ("alec_koff-carnaval-484622.mp3", "Carnaval Drive"),
        ("fassounds-escape-your-love-upbeat-fashion-pop-dance-412230.mp3", "Upbeat Fashion Pop"),
        ("ikoliks_aj-acoustic-spring-mothers-day-music-320427.mp3", "Acoustic Spring"),
        ("kontraa-water-afro-pop-music-445661.mp3", "Afro Pop Groove"),
    ]

    def handle(self, *args, **options):
        media_root = settings.MEDIA_ROOT
        music_dir = os.path.join(media_root, 'music')

        created_count = 0
        for filename, title in self.DEFAULT_TRACKS:
            rel_path = f"music/{filename}"
            full_path = os.path.join(music_dir, filename)

            # Check if file exists on disk
            if not os.path.exists(full_path):
                self.stdout.write(self.style.WARNING(f"File not found on disk: {full_path} (skipping)"))
                continue

            obj, created = Music.objects.get_or_create(
                file=rel_path,
                defaults={'title': title}
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created music track: '{title}' (ID: {obj.id})"))
            else:
                self.stdout.write(f"Track already exists: '{obj.title}' (ID: {obj.id})")

        self.stdout.write(self.style.SUCCESS(f"Finished! {created_count} new track(s) seeded. Total in DB: {Music.objects.count()}"))
