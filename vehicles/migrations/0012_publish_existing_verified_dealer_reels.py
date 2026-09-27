import os
import re
from django.db import migrations

AI_VIDEO_FILENAME_RE = re.compile(r'ai_gen_([a-f0-9\-]{36})', re.IGNORECASE)
AI_TEMP_REEL_FILENAME_RE = re.compile(r'^vehicle_reel(_[a-zA-Z0-9]+)*\.mp4$', re.IGNORECASE)


def publish_and_backfill_reels(apps, schema_editor):
    Vehicle = apps.get_model('vehicles', 'Vehicle')
    DealerVehicleReel = apps.get_model('vehicles', 'DealerVehicleReel')

    # Publish existing vehicles that already have reels uploaded by verified dealers
    Vehicle.objects.filter(
        is_draft=True,
        dealer__business_info__verification_status='verified',
        reels__isnull=False,
    ).update(is_draft=False)

    # Ensure is_ai_generated=True on any reels with vehicle_reel_*_stream.mp4 or ai_gen_*_stream.mp4
    for reel in DealerVehicleReel.objects.filter(is_ai_generated=False):
        filename = os.path.basename(getattr(reel.video_file, 'name', '') or '')
        if reel.ai_generation_id is not None or AI_VIDEO_FILENAME_RE.search(filename) or AI_TEMP_REEL_FILENAME_RE.match(filename):
            reel.is_ai_generated = True
            reel.save(update_fields=['is_ai_generated'])


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0011_backfill_ai_generated_reels'),
    ]

    operations = [
        migrations.RunPython(publish_and_backfill_reels, migrations.RunPython.noop),
    ]
