"""
Client helpers for the external car-video-agent (FastAPI) service.

Django's job here is only to hand off the dealer's images + prompt to that
service and, later, receive the finished video via webhook. The actual
generation (fal.ai Kling model + OpenAI vision) lives entirely in that
separate service.
"""
import httpx
import requests
from django.conf import settings
from django.core.files.base import ContentFile


def dispatch_video_generation(generation, images):
    """
    Forwards a generation job to the car-video-agent /generate endpoint.

    Returns True if the job was accepted (generation.status becomes
    'processing'); returns False and marks the generation 'failed' if the
    service could not be reached or rejected the request.
    """
    service_url = (getattr(settings, 'AI_VIDEO_SERVICE_URL', '') or '').rstrip('/')
    if not service_url:
        generation.status = 'failed'
        generation.error_message = "AI_VIDEO_SERVICE_URL is not configured."
        generation.save()
        return False

    files = [
        ('images', (img.name, img.read(), img.content_type or 'application/octet-stream'))
        for img in images
    ]
    data = {
        'job_id': str(generation.job_id),
        'duration': generation.duration,
        'resolution': generation.resolution,
    }
    if generation.prompt:
        data['prompt'] = generation.prompt

    try:
        response = httpx.post(f"{service_url}/generate", data=data, files=files, timeout=30)
        response.raise_for_status()
    except Exception as e:
        generation.status = 'failed'
        generation.error_message = f"Failed to dispatch AI video generation: {str(e)}"
        generation.save()
        return False

    generation.status = 'processing'
    generation.save()
    return True


def download_generated_video(generation, video_url):
    """
    Downloads the finished video from the URL the car-video-agent service
    reported (a fal.ai media URL) and attaches it to the generation record.
    """
    try:
        response = requests.get(video_url, timeout=60)
        response.raise_for_status()
    except Exception as e:
        generation.error_message = f"Failed to download generated video: {str(e)}"
        generation.save()
        return False

    file_name = f"ai_gen_{generation.job_id}.mp4"
    generation.generated_video.save(file_name, ContentFile(response.content), save=False)
    return True
