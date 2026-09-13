import os
import random
from concurrent.futures import ThreadPoolExecutor
import httpx
import fal_client
from openai import OpenAI
from core.config import FAL_KEY, OPENAI_API_KEY, BACKEND_WEBHOOK_URL
from agent.schemas import VideoResultPayload

os.environ["FAL_KEY"] = FAL_KEY

openai_client = OpenAI(api_key=OPENAI_API_KEY)

KLING_ENDPOINT = "fal-ai/kling-video/v3/pro/image-to-video"

DEFAULT_SCENES = [
    "driving smoothly on a coastal highway at sunset",
    "descending a mountain road, golden hour lighting",
    "driving through a desert landscape, dust trailing behind",
]

IDENTITY_LOCK_HEADER = """@Element1=reference car. KEEP IDENTICAL: {detected_description}, color={detected_color}, wheels, badges, body lines. NO substitution."""


def _resolve_scene(prompt: str | None) -> str:
    if prompt and prompt.strip():
        return prompt.strip()
    return random.choice(DEFAULT_SCENES)


def _detect_car_description(image_url: str) -> tuple[str, str]:
    response = openai_client.chat.completions.create(
        model="gpt-5.6-luna",
        # This is a trivial single-label classification, not a task that
        # benefits from reasoning — and gpt-5.6-luna defaults to "medium"
        # reasoning effort, whose hidden reasoning tokens count against
        # max_completion_tokens. With a low budget that can consume the
        # entire completion and leave message.content empty. Disabling
        # reasoning also makes this call faster.
        reasoning_effort="none",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Identify this car. Respond in this EXACT format with no extra text:\n"
                            "BRAND MODEL, BODY_TYPE | EXACT_COLOR\n"
                            "Be very specific about the color (e.g. 'matte black', 'pearl white', "
                            "'metallic silver'). If brand/model is not identifiable, describe the "
                            "body shape in detail instead."
                        )
                    },
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ],
        max_completion_tokens=150
    )

    text = (response.choices[0].message.content or "").strip()
    if "|" in text:
        desc, color = text.split("|", 1)
        return desc.strip() or "the reference car", color.strip() or "as shown in the reference image"
    return text or "the reference car", "as shown in the reference image"


# fal.ai's Kling API rejects a shot prompt with "size must be between 0 and
# 512" once it's too long. We've now seen it reject a prompt at exactly 512
# UTF-8 bytes, and separately one at exactly 512 Python characters — so the
# real limit is stricter than "<= 512" in whichever unit fal actually counts
# (most likely an exclusive upper bound, i.e. 511 is the true max). Rather
# than keep guessing the exact boundary, stay safely under it with real margin.
FAL_PROMPT_SAFETY_LIMIT = 480


def _truncate_to_limit(text: str, max_len: int) -> str:
    """Truncate text to at most max_len characters."""
    return text if len(text) <= max_len else text[:max_len]


def _build_multi_prompt(identity_header: str, client_scene: str, total_duration: int) -> list[dict]:
    per_shot = max(3, total_duration // 4)

    # Only Shot 1 embeds the dealer's free-text scene/prompt verbatim — a
    # long custom prompt can push it past fal.ai's prompt-length limit,
    # which fails the whole job. Trim it to fit, preserving as much of the
    # dealer's wording as possible instead of failing outright.
    shot1_prefix = f"{identity_header}\nShot 1 — Front three-quarter view of the car, "
    shot1_suffix = "."
    scene_budget = max(FAL_PROMPT_SAFETY_LIMIT - len(shot1_prefix) - len(shot1_suffix), 0)
    trimmed_scene = _truncate_to_limit(client_scene, scene_budget).rstrip()

    shots = [
        f"{shot1_prefix}{trimmed_scene}{shot1_suffix}",
        f"{identity_header}\nShot 2 — Left side profile view of the same car, continuing the scene.",
        f"{identity_header}\nShot 3 — Right side profile view of the same car, continuing the scene.",
        f"{identity_header}\nShot 4 — Rear view of the same car, continuing the scene.",
    ]
    # Safety net in case identity_header itself ever grows unexpectedly long.
    shots = [_truncate_to_limit(s, FAL_PROMPT_SAFETY_LIMIT) for s in shots]
    return [{"prompt": s, "duration": str(per_shot)} for s in shots]


def run_video_generation(job_id: str, prompt: str | None, image_paths: list[str],
                          duration: str = "10", resolution: str = "720p"):
    try:
        client_scene = _resolve_scene(prompt)

        # First image = start frame, next up to 3 = reference angles for the
        # element (Kling API caps reference images at 3) — anything beyond
        # the 4th image is never used, so we don't waste time uploading it.
        upload_paths = image_paths[:4]

        # Upload the start frame first; the remaining reference-image
        # uploads and the identity-detection call (which only needs the
        # start frame) are independent of each other, so run them all
        # concurrently instead of one after another.
        start_image_url = fal_client.upload_file(upload_paths[0])

        with ThreadPoolExecutor(max_workers=4) as executor:
            detection_future = executor.submit(_detect_car_description, start_image_url)
            reference_futures = [executor.submit(fal_client.upload_file, path) for path in upload_paths[1:]]

            reference_image_urls = [f.result() for f in reference_futures]
            detected_description, detected_color = detection_future.result()

        print(f"[job {job_id}] detected: {detected_description} | {detected_color}")

        identity_header = IDENTITY_LOCK_HEADER.format(
            detected_description=detected_description,
            detected_color=detected_color
        )

        multi_prompt = _build_multi_prompt(identity_header, client_scene, int(duration))

        result = fal_client.subscribe(
            KLING_ENDPOINT,
            arguments={
                "start_image_url": start_image_url,
                "multi_prompt": multi_prompt,
                "shot_type": "customize",
                "elements": [
                    {
                        "frontal_image_url": start_image_url,
                        "reference_image_urls": reference_image_urls
                    }
                ],
                "duration": duration,
                "generate_audio": False
            },
            with_logs=True,
            on_queue_update=lambda update: print(f"[job {job_id}]", update)
        )

        video_url = result["video"]["url"]
        payload = VideoResultPayload(job_id=job_id, status="completed", video_url=video_url)

    except Exception as e:
        payload = VideoResultPayload(job_id=job_id, status="failed", error=str(e))

    finally:
        for path in image_paths:
            try:
                os.remove(path)
            except OSError:
                pass

    _push_to_backend(payload)


def _push_to_backend(payload: VideoResultPayload):
    try:
        response = httpx.post(BACKEND_WEBHOOK_URL, json=payload.model_dump(), timeout=30)
        # A non-2xx response (e.g. 401 from a mismatched webhook token) means
        # Django never recorded the result -- without raise_for_status() that
        # failure was invisible: the request "succeeded" as far as httpx.post
        # is concerned, so the except branch below never ran and nothing was
        # ever logged. The job then sits in "processing" forever with no
        # trace of what went wrong.
        response.raise_for_status()
    except Exception as e:
        print(f"[video_agent] Failed to push result for job {payload.job_id}: {e}")