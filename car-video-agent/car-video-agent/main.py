from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="Car AI Video Agent")

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}