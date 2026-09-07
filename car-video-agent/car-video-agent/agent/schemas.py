# agent/schemas.py

from pydantic import BaseModel, HttpUrl
from typing import List
from typing import Optional


class VideoGenerateRequest(BaseModel):
    job_id: str
    prompt: str
    image_urls: List[HttpUrl]   # max 10 enforced in route validation
    duration: str = "10"
    resolution: str = "720p"


class VideoGenerateResponse(BaseModel):
    job_id: str
    status: str

class VideoResultPayload(BaseModel):
    job_id: str
    status: str
    video_url: Optional[str] = None
    error: Optional[str] = None