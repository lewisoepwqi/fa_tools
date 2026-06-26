from fastapi import FastAPI

from app.api.routes import files

app = FastAPI(title="FA Tools API", version="0.1.0")
app.include_router(files.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
