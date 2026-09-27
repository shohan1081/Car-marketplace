import hashlib
import os
import re
from django.db import migrations

AI_VIDEO_FILENAME_RE = re.compile(r'ai_gen_([a-f0-9\-]{36})', re.IGNORECASE)
AI_TEMP_REEL_FILENAME_RE = re.compile(r'^vehicle_reel(_[a-zA-Z0-9]+)?\.mp4$', re.IGNORECASE)


def _compute_file_sha256(file_field):
    if not file_field:
        return None
    hasher = hashlib.sha256()
    try:
        with file_field.open('rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None


def backfill_ai_generated_reels(apps, schema_editor):
    DealerVehicleReel = apps.get_model('vehicles', 'DealerVehicleReel')
    AIVideoGeneration = apps.get_model('vehicles', 'AIVideoGeneration')

    # Pre-index completed AIVideoGenerations by (dealer_id, size, sha256) where possible
    gen_by_job_id = {}
    gen_hash_index = {}
    for gen in AIVideoGeneration.objects.all():
        gen_by_job_id[str(gen.job_id).lower()] = gen
        if gen.status == 'completed' and gen.generated_video:
            try:
                size = gen.generated_video.size
                digest = _compute_file_sha256(gen.generated_video)
                if size and digest:
                    gen_hash_index[(size, digest)] = gen
            except Exception:
                pass

    for reel in DealerVehicleReel.objects.all().order_by('created_at'):
        updated_fields = []
        filename = os.path.basename(getattr(reel.video_file, 'name', '') or '')

        # 1. Already linked to an AIVideoGeneration
        if reel.ai_generation_id is not None and not reel.is_ai_generated:
            reel.is_ai_generated = True
            updated_fields.append('is_ai_generated')

        # 2. Filename contains ai_gen_<uuid>
        match = AI_VIDEO_FILENAME_RE.search(filename)
        if match:
            job_id_str = match.group(1).lower()
            matched_gen = gen_by_job_id.get(job_id_str)
            if not reel.is_ai_generated:
                reel.is_ai_generated = True
                updated_fields.append('is_ai_generated')
            if matched_gen and reel.ai_generation_id is None:
                reel.ai_generation_id = matched_gen.id
                updated_fields.append('ai_generation')

        # 3. Exact file size + SHA-256 match against completed AIVideoGeneration
        if not reel.is_ai_generated and reel.video_file and gen_hash_index:
            try:
                size = reel.video_file.size
                if any(s == size for (s, _) in gen_hash_index.keys()):
                    digest = _compute_file_sha256(reel.video_file)
                    matched_gen = gen_hash_index.get((size, digest))
                    if matched_gen:
                        reel.is_ai_generated = True
                        updated_fields.append('is_ai_generated')
                        if reel.ai_generation_id is None:
                            reel.ai_generation_id = matched_gen.id
                            updated_fields.append('ai_generation')
            except Exception:
                pass

        # 4. Flutter downloaded AI temp filename (`vehicle_reel.mp4` / `vehicle_reel_<suffix>.mp4`)
        if not reel.is_ai_generated and AI_TEMP_REEL_FILENAME_RE.match(filename):
            reel.is_ai_generated = True
            updated_fields.append('is_ai_generated')
            if reel.ai_generation_id is None:
                unused_gen = (
                    AIVideoGeneration.objects.filter(
                        dealer_id=reel.dealer_id,
                        status='completed',
                        reels__isnull=True,
                        created_at__lte=reel.created_at,
                    )
                    .order_by('-created_at')
                    .first()
                )
                if unused_gen:
                    reel.ai_generation_id = unused_gen.id
                    updated_fields.append('ai_generation')

        if updated_fields:
            reel.save(update_fields=list(dict.fromkeys(updated_fields)))


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0010_dealervehiclereel_ai_generation_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_ai_generated_reels, migrations.RunPython.noop),
    ]
