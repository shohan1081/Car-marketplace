import os
import shutil
import subprocess
import tempfile
from django.core.exceptions import ValidationError


def _probe_duration_seconds(path):
    ffprobe_bin = shutil.which('ffprobe')
    if ffprobe_bin:
        out = subprocess.run(
            [
                ffprobe_bin, '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                path,
            ],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.strip()
        return float(out)

    from moviepy import VideoFileClip
    clip = VideoFileClip(path)
    try:
        return float(clip.duration or 0)
    finally:
        clip.close()


def validate_video_duration(video_file):
    """
    Validate that the video duration is less than 60 seconds.
    Uses TemporaryUploadedFile's on-disk path directly when available to avoid
    duplicating large uploads on disk, and uses ffprobe for fast header inspection.
    """
    cleanup_path = None
    if hasattr(video_file, 'temporary_file_path'):
        tmp_path = video_file.temporary_file_path()
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(video_file.name)[1]) as tmp:
            for chunk in video_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
            cleanup_path = tmp_path

    try:
        duration = _probe_duration_seconds(tmp_path)
        if duration > 60:
            raise ValidationError(f"Video duration ({duration:.2f}s) exceeds the 60-second limit for reels.")
    except Exception as e:
        if isinstance(e, ValidationError):
            raise e
        raise ValidationError(f"Could not analyze video: {str(e)}")
    finally:
        if cleanup_path and os.path.exists(cleanup_path):
            os.remove(cleanup_path)

