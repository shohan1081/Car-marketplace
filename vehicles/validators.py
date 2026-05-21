import os
import tempfile
from django.core.exceptions import ValidationError
from moviepy import VideoFileClip

def validate_video_duration(video_file):
    """
    Validate that the video duration is less than 60 seconds.
    """
    # Create a temporary file to save the uploaded content
    # MoviePy needs a file path to read metadata
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(video_file.name)[1]) as tmp:
        for chunk in video_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        clip = VideoFileClip(tmp_path)
        duration = clip.duration
        clip.close()
        
        if duration > 60:
            raise ValidationError(f"Video duration ({duration:.2f}s) exceeds the 60-second limit for reels.")
            
    except Exception as e:
        if isinstance(e, ValidationError):
            raise e
        raise ValidationError(f"Could not analyze video: {str(e)}")
    finally:
        # Clean up the temporary file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
