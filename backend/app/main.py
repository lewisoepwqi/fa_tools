from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audit, auth, files
from app.core.config import get_settings
from app.tools.bank_journal import register as register_bank_journal

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
# 平台共享路由（认证、文件上传、审计日志）。
app.include_router(auth.router)
app.include_router(audit.router)
app.include_router(files.router)
# 工具：银行流水转公司日记账（新增工具时在此注册其 register 函数）。
register_bank_journal(app)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
