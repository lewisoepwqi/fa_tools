from fastapi import FastAPI

from app.api.routes import (
    bank_templates,
    conversion_runs,
    exports,
    files,
    journal_templates,
    mapping_profiles,
    preview_rows,
    rules,
)

app = FastAPI(title="FA Tools API", version="0.1.0")
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
