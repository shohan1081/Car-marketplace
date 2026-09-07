from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
from typing import List, Optional
from agent.schemas import VideoGenerateResponse
from agent.video_agent import run_video_generation
import shutil
import tempfile
import os

router = APIRouter()

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".avif"}


@router.post("/generate", response_model=VideoGenerateResponse)
async def generate_video(
    background_tasks: BackgroundTasks,
    job_id: str = Form(...),
    prompt: Optional[str] = Form(None),
    duration: str = Form("10"),
    resolution: str = Form("720p"),
    images: List[UploadFile] = File(...)
):
    if len(images) > 7:
        raise HTTPException(status_code=400, detail="Maximum 7 images allowed")

    if len(images) < 1:
        raise HTTPException(status_code=400, detail="At least 1 image is required")

    temp_paths = []

    for img in images:
        ext = os.path.splitext(img.filename)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {ext}. Allowed: PNG, JPG, JPEG, WEBP, AVIF"
            )

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        shutil.copyfileobj(img.file, tmp)
        tmp.close()
        temp_paths.append(tmp.name)

    background_tasks.add_task(
        run_video_generation,
        job_id=job_id,
        prompt=prompt,
        image_paths=temp_paths,
        duration=duration,
        resolution=resolution
    )

    return VideoGenerateResponse(job_id=job_id, status="processing")