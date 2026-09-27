"""
Background video optimization for mobile streaming.

Uploaded videos are often phone/camera exports: 1080p+ at 10-20 Mbps with the MP4
index ('moov' atom) at the END of the file. Streamed over mobile data that means
the player must fetch the end of the file before it can start, and then cannot
download fast enough to keep up -> constant buffering.

After a `video_file` (or `generated_video`) changes, this module re-encodes it
with ffmpeg to:
  - H.264 (High, level 4.0) + AAC, universally supported on iOS/Android
  - short side capped at 720px, bitrate capped (~2.5 Mbps by default)
  - `+faststart` so playback starts immediately and seeking works
and swaps the model's video field to the optimized copy, deleting the original.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading

from django.apps import apps
from django.conf import settings
from django.core.files import File
from django.db import models, transaction
from django.db.models import Q
from django.db.models.signals import post_init, post_save

logger = logging.getLogger(__name__)

VIDEO_FIELD = 'video_file'
VIDEO_FIELDS = ('video_file', 'generated_video')
OPTIMIZED_SUFFIX = '_stream.mp4'
LOCK_FILE = os.path.join(tempfile.gettempdir(), 'video_optimize.lock')

_thread_lock = threading.Lock()


def _setting(name, default):
    return getattr(settings, name, default)


def ffmpeg_available():
    return bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))


def needs_optimization(name):
    name = str(name or '')
    return bool(name) and not name.startswith(('http://', 'https://')) and not name.endswith(OPTIMIZED_SUFFIX)


class _ProcessLock:
    """Only one ffmpeg job at a time across all Gunicorn workers (protects CPU/RAM)."""

    def __enter__(self):
        _thread_lock.acquire()
        self._fh = open(LOCK_FILE, 'w')
        try:
            import fcntl
            fcntl.flock(self._fh, fcntl.LOCK_EX)
        except ImportError:  # Windows dev machine
            pass
        return self

    def __exit__(self, *exc):
        self._fh.close()
        _thread_lock.release()


def _source_path(storage, name):
    try:
        return storage.path(name)
    except NotImplementedError:
        return storage.url(name)  # presigned S3/CDN URL; ffmpeg reads it with HTTP range requests


def _probe(source):
    out = subprocess.run(
        [shutil.which('ffprobe'), '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', source],
        capture_output=True, text=True, timeout=120, check=True,
    ).stdout
    info = json.loads(out)
    video = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), None)
    audio = next((s for s in info.get('streams', []) if s.get('codec_type') == 'audio'), None)
    return info.get('format', {}), video, audio


def _ffmpeg_command(source, target, fmt, video, audio):
    max_short_side = int(_setting('VIDEO_OPTIMIZE_MAX_SHORT_SIDE', 720))
    max_kbps = int(_setting('VIDEO_OPTIMIZE_MAX_KBPS', 2500))

    width, height = int(video.get('width') or 0), int(video.get('height') or 0)
    bitrate_kbps = int(fmt.get('bit_rate') or 0) // 1000
    already_streamable = (
        video.get('codec_name') == 'h264'
        and video.get('pix_fmt') == 'yuv420p'
        and min(width, height) <= max_short_side
        and 0 < bitrate_kbps <= max_kbps * 1.3
        and (audio is None or audio.get('codec_name') == 'aac')
    )

    cmd = [shutil.which('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-y', '-i', source]
    if already_streamable:
        # Just move the moov atom to the front; no quality loss, takes seconds.
        cmd += ['-map', '0:v:0', '-map', '0:a:0?', '-c', 'copy']
    else:
        # Cap the short side (portrait or landscape), never upscale, keep even dimensions.
        scale = (
            f"scale=w=if(gt(iw\\,ih)\\,-2\\,min({max_short_side}\\,iw))"
            f":h=if(gt(iw\\,ih)\\,min({max_short_side}\\,ih)\\,-2)"
        )
        cmd += [
            '-map', '0:v:0', '-map', '0:a:0?',
            '-vf', scale,
            '-c:v', 'libx264', '-preset', _setting('VIDEO_OPTIMIZE_PRESET', 'veryfast'),
            '-crf', str(_setting('VIDEO_OPTIMIZE_CRF', 23)),
            '-maxrate', f'{max_kbps}k', '-bufsize', f'{max_kbps * 2}k',
            '-profile:v', 'high', '-level:v', '4.0', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '128k', '-ac', '2',
            '-threads', str(_setting('VIDEO_OPTIMIZE_THREADS', 2)),
        ]
    cmd += ['-movflags', '+faststart', target]
    return cmd


def _get_model_video_field_name(model):
    for field_name in VIDEO_FIELDS:
        if any(f.name == field_name and isinstance(f, models.FileField) for f in model._meta.fields):
            return field_name
    return VIDEO_FIELD


def optimize_video(model, pk, expected_name, field_name=None):
    """
    Re-encode `model(pk).<video_field>` for streaming. Safe to call repeatedly:
    it only swaps the file if the row still points at `expected_name`.
    Returns the new storage name, or None if nothing was done.
    """
    if not ffmpeg_available():
        logger.warning("ffmpeg/ffprobe not installed; skipping video optimization for %s", expected_name)
        return None

    field_name = field_name or _get_model_video_field_name(model)
    field = model._meta.get_field(field_name)
    storage = field.storage

    with _ProcessLock():
        if not model.objects.filter(pk=pk, **{field_name: expected_name}).exists():
            return None  # replaced or deleted meanwhile

        source = _source_path(storage, expected_name)
        fd, target = tempfile.mkstemp(suffix='.mp4')
        os.close(fd)
        try:
            fmt, video, audio = _probe(source)
            if video is None:
                logger.warning("No video stream found in %s; skipping optimization", expected_name)
                return None

            cmd = _ffmpeg_command(source, target, fmt, video, audio)
            nice = ['nice', '-n', '10'] if os.name == 'posix' and shutil.which('nice') else []
            subprocess.run(nice + cmd, check=True, timeout=int(_setting('VIDEO_OPTIMIZE_TIMEOUT', 3600)))

            base = os.path.splitext(expected_name)[0]
            with open(target, 'rb') as fh:
                new_name = storage.save(base + OPTIMIZED_SUFFIX, File(fh))

            updates = {field_name: new_name}
            duration = int(float(fmt.get('duration') or 0))
            if duration and any(f.name == 'duration_seconds' for f in model._meta.fields):
                if model.objects.filter(Q(duration_seconds=0) | Q(duration_seconds__isnull=True), pk=pk).exists():
                    updates['duration_seconds'] = duration

            if model.objects.filter(pk=pk, **{field_name: expected_name}).update(**updates):
                storage.delete(expected_name)
                logger.info(
                    "Optimized video %s -> %s (%.1f MB -> %.1f MB)",
                    expected_name, new_name,
                    int(fmt.get('size') or 0) / 1048576, os.path.getsize(target) / 1048576,
                )
                return new_name

            storage.delete(new_name)  # row changed while we were encoding
            return None
        finally:
            if os.path.exists(target):
                os.remove(target)


def _run_in_background(model, pk, name, field_name):
    def job():
        try:
            optimize_video(model, pk, name, field_name=field_name)
        except Exception:
            logger.exception("Video optimization failed for %s pk=%s (%s)", model.__name__, pk, name)
    threading.Thread(target=job, name=f'optimize-video-{pk}', daemon=True).start()


def _raw_name(instance, field_name):
    # Read __dict__ directly so deferred fields (.only()/.defer()) don't trigger a query.
    value = instance.__dict__.get(field_name)
    return str(getattr(value, 'name', value) or '')


def _remember_original(sender, instance, **kwargs):
    field_name = _get_model_video_field_name(sender)
    instance._original_video_name = _raw_name(instance, field_name) if instance.pk else None


def _schedule_if_changed(sender, instance, **kwargs):
    field_name = _get_model_video_field_name(sender)
    if field_name not in instance.__dict__:
        return
    name = _raw_name(instance, field_name)
    changed = name != getattr(instance, '_original_video_name', None)
    instance._original_video_name = name
    if changed and needs_optimization(name):
        transaction.on_commit(lambda: _run_in_background(sender, instance.pk, name, field_name))


def video_models():
    return [
        m for m in apps.get_models()
        if any(f.name in VIDEO_FIELDS and isinstance(f, models.FileField) for f in m._meta.fields)
    ]


def connect_signals():
    if not _setting('VIDEO_AUTO_OPTIMIZE', True):
        return
    for model in video_models():
        post_init.connect(_remember_original, sender=model, dispatch_uid=f'video_opt_init_{model._meta.label}')
        post_save.connect(_schedule_if_changed, sender=model, dispatch_uid=f'video_opt_save_{model._meta.label}')
