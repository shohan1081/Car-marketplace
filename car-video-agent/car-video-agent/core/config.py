# core/config.py

import os
from dotenv import load_dotenv

load_dotenv()

FAL_KEY = os.getenv("FAL_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BACKEND_WEBHOOK_URL = os.getenv("BACKEND_WEBHOOK_URL")

if not FAL_KEY:
    raise RuntimeError("FAL_KEY is missing in .env")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing in .env")

if not BACKEND_WEBHOOK_URL:
    raise RuntimeError("BACKEND_WEBHOOK_URL is missing in .env")