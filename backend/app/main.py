from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    audit,
    bank_templates,
    conversion_runs,
    exports,
    files,
    journal_templates,
    mapping_profiles,
    preview_rows,
    rules,
)
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="FA Tools API", version="0.1.0")
# 前端 dev server (5173) 跨域访问后端 API。仅放行配置中的来源。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(audit.router)
app.include_router(files.router)
app.include_router(bank_templates.router)
app.include_router(journal_templates.router)
app.include_router(mapping_profiles.router)
app.include_router(rules.router)
app.include_router(conversion_runs.router)
app.include_router(preview_rows.router)
app.include_router(exports.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
