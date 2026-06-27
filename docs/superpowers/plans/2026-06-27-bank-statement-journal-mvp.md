# Bank Statement Journal MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working B/S MVP that uploads bank statement files, normalizes them into standard bank transactions, applies versioned templates, mappings, and rules, previews journal rows for manual confirmation, and exports the company journal file.

**Architecture:** Use a monorepo with a FastAPI backend, PostgreSQL persistence, local file storage for MVP, and a React + TypeScript + Ant Design frontend. Keep financial transformation logic in pure Python services with unit tests before exposing it through API routes. Persist immutable template, mapping, and rule versions so each conversion run remains traceable.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, pytest, openpyxl, pandas only where helpful for file IO, React, TypeScript, Vite, Ant Design, Vitest, Playwright.

---

## Scope

This plan implements the MVP described in:

- `docs/prd-bank-statement-journal.md`
- `docs/technical-design-bank-statement-journal.md`

Included in this plan:

1. Local development setup.
2. Backend domain models and database migrations.
3. File upload and local storage.
4. CSV/XLSX parsing.
5. Header detection and amount/date normalization.
6. Immutable bank template, company journal template, mapping, and rule versions.
7. Rule matching and conflict detection.
8. Conversion run creation and preview row generation.
9. Manual adjustment and confirmation.
10. CSV/XLSX export and processing report.
11. Minimal auth/RBAC suitable for MVP development.
12. React UI for the main workflow.
13. Unit, integration, and end-to-end tests.

Excluded from this plan:

1. OCR for PDF/OFD/image files.
2. Bank direct connection.
3. ERP write-back.
4. Full bank-to-general-ledger reconciliation.
5. Machine-learning rule recommendation.

---

## Target File Structure

Create this structure from an empty repository:

```text
.
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docs/
│   ├── prd-bank-statement-journal.md
│   ├── technical-design-bank-statement-journal.md
│   └── superpowers/plans/2026-06-27-bank-statement-journal-mvp.md
├── backend/
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── audit.py
│   │   │       ├── bank_templates.py
│   │   │       ├── conversion_runs.py
│   │   │       ├── exports.py
│   │   │       ├── files.py
│   │   │       ├── journal_templates.py
│   │   │       ├── mapping_profiles.py
│   │   │       ├── preview_rows.py
│   │   │       └── rules.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── crypto.py
│   │   │   ├── enums.py
│   │   │   └── security.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── session.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── audit.py
│   │   │   ├── company.py
│   │   │   ├── conversion.py
│   │   │   ├── file.py
│   │   │   ├── mapping.py
│   │   │   ├── rule.py
│   │   │   ├── template.py
│   │   │   └── user.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── audit.py
│   │   │   ├── conversion.py
│   │   │   ├── file.py
│   │   │   ├── mapping.py
│   │   │   ├── rule.py
│   │   │   ├── standard.py
│   │   │   └── template.py
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── audit_service.py
│   │       ├── confirmation_service.py
│   │       ├── conversion_service.py
│   │       ├── export_service.py
│   │       ├── file_service.py
│   │       ├── mapping_service.py
│   │       ├── parser_service.py
│   │       ├── rule_service.py
│   │       └── template_service.py
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   └── tests/
│       ├── conftest.py
│       ├── fixtures/
│       │   ├── bank_statement_basic.csv
│       │   └── bank_statement_basic.xlsx
│       ├── integration/
│       │   ├── test_conversion_api.py
│       │   └── test_export_api.py
│       └── unit/
│           ├── test_export_service.py
│           ├── test_mapping_service.py
│           ├── test_parser_service.py
│           ├── test_rule_service.py
│           └── test_template_service.py
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    ├── src/
    │   ├── App.tsx
    │   ├── main.tsx
    │   ├── api/
    │   │   ├── client.ts
    │   │   ├── conversionRuns.ts
    │   │   ├── files.ts
    │   │   ├── rules.ts
    │   │   └── templates.ts
    │   ├── components/
    │   │   ├── AppShell.tsx
    │   │   ├── ExceptionTag.tsx
    │   │   ├── StatusTag.tsx
    │   │   └── VersionBadge.tsx
    │   ├── pages/
    │   │   ├── AuditLogPage.tsx
    │   │   ├── BankTemplatePage.tsx
    │   │   ├── ConversionRunDetailPage.tsx
    │   │   ├── ConversionRunListPage.tsx
    │   │   ├── JournalTemplatePage.tsx
    │   │   ├── MappingProfilePage.tsx
    │   │   ├── RulePage.tsx
    │   │   └── UploadPage.tsx
    │   ├── types/
    │   │   ├── conversion.ts
    │   │   ├── rule.ts
    │   │   └── template.ts
    │   └── styles.css
    └── tests/
        ├── app.spec.ts
        └── conversion-flow.spec.ts
```

---

## Implementation Principles

1. Domain logic first, API second, UI third.
2. Pure transformation services must be tested without a database.
3. Version records are immutable after creation.
4. Every preview row keeps enough trace data to explain its output.
5. Default behavior is conservative: uncertain rows require confirmation.
6. Use local file storage in MVP, but keep a `FileService` boundary so S3/MinIO can replace it later.
7. Do not introduce asynchronous workers until the synchronous conversion path is passing tests. Add the queue in a later hardening pass.

---

## Task 1: Initialize Repository and Developer Tooling

**Files:**

- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `docker-compose.yml`
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Initialize git if needed**

Run:

```bash
git rev-parse --is-inside-work-tree || git init
```

Expected: either `true` or a new repository initialized in `/home/lewis/coding/fa_tools`.

- [ ] **Step 2: Create backend package and dependency manifest**

Create `backend/pyproject.toml` with:

```toml
[project]
name = "fa-tools-backend"
version = "0.1.0"
description = "Financial automation tools backend"
requires-python = ">=3.12"
dependencies = [
  "alembic>=1.13.2",
  "fastapi>=0.115.0",
  "openpyxl>=3.1.5",
  "passlib[bcrypt]>=1.7.4",
  "pydantic-settings>=2.4.0",
  "python-jose[cryptography]>=3.3.0",
  "python-multipart>=0.0.9",
  "sqlalchemy>=2.0.32",
  "uvicorn[standard]>=0.30.6",
]

[project.optional-dependencies]
dev = [
  "httpx>=0.27.2",
  "pytest>=8.3.2",
  "pytest-cov>=5.0.0",
  "ruff>=0.6.3",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 3: Create app entrypoint**

Create `backend/app/main.py` with:

```python
from fastapi import FastAPI

app = FastAPI(title="FA Tools API", version="0.1.0")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Add local environment and Docker services**

Create `.env.example` with:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+psycopg://fa_tools:fa_tools@localhost:5432/fa_tools
TEST_DATABASE_URL=sqlite+pysqlite:///:memory:
SECRET_KEY=replace-this-in-production
UPLOAD_DIR=.local/uploads
EXPORT_DIR=.local/exports
```

Create `docker-compose.yml` with:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: fa_tools
      POSTGRES_USER: fa_tools
      POSTGRES_PASSWORD: fa_tools
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

- [ ] **Step 5: Add root README and ignore rules**

Create `.gitignore` with:

```gitignore
.env
.local/
.pytest_cache/
.ruff_cache/
__pycache__/
*.pyc
backend/.coverage
backend/htmlcov/
frontend/node_modules/
frontend/dist/
```

Create `README.md` with:

```markdown
# FA Tools

财务通用工具包。第一个 MVP 是银行流水转公司日记账。

## Local Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```
```

- [ ] **Step 6: Add backend test harness**

Create `backend/tests/conftest.py` with:

```python
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 7: Verify backend starts under test**

Run:

```bash
cd backend && pip install -e ".[dev]" && pytest -q
```

Expected: pytest exits successfully with no collected tests or only future tests after later tasks.

- [ ] **Step 8: Commit**

Run:

```bash
git add .gitignore .env.example README.md docker-compose.yml backend
git commit -m "chore: initialize fa tools project"
```

Expected: commit succeeds.

---

## Task 2: Add Core Configuration, Enums, and Standard Schemas

**Files:**

- Create: `backend/app/core/config.py`
- Create: `backend/app/core/enums.py`
- Create: `backend/app/schemas/standard.py`
- Test: `backend/tests/unit/test_parser_service.py`

- [ ] **Step 1: Write tests for standard transaction validation**

Create `backend/tests/unit/test_parser_service.py` with:

```python
from decimal import Decimal

from app.core.enums import TransactionDirection
from app.schemas.standard import StandardBankTransaction


def test_standard_bank_transaction_accepts_credit_amount() -> None:
    transaction = StandardBankTransaction(
        transaction_date="2026-06-01",
        posting_date="2026-06-01",
        bank_account_id="bank-account-1",
        currency="CNY",
        direction=TransactionDirection.CREDIT,
        debit_amount=None,
        credit_amount=Decimal("12000.00"),
        net_amount=Decimal("12000.00"),
        balance=Decimal("98000.00"),
        counterparty_name="某客户有限公司",
        counterparty_account_no="6222000000000000",
        counterparty_bank_name="某银行某支行",
        summary="货款",
        purpose="6月服务费",
        transaction_type="转账",
        bank_transaction_id="202606010001",
        receipt_no=None,
        source_file_id="file-1",
        source_sheet_name="Sheet1",
        source_row_index=2,
        raw_row={"收入": "12000.00"},
    )

    assert transaction.direction == TransactionDirection.CREDIT
    assert transaction.net_amount == Decimal("12000.00")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/unit/test_parser_service.py -q
```

Expected: FAIL because `app.core.enums` and `app.schemas.standard` do not exist.

- [ ] **Step 3: Implement config and enums**

Create `backend/app/core/config.py` with:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite+pysqlite:///:memory:"
    test_database_url: str = "sqlite+pysqlite:///:memory:"
    secret_key: str = "development-secret"
    upload_dir: str = ".local/uploads"
    export_dir: str = ".local/exports"

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Create `backend/app/core/enums.py` with:

```python
from enum import StrEnum


class RecordStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class FileStatus(StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class TransactionDirection(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class AmountMode(StrEnum):
    SINGLE_AMOUNT_WITH_DIRECTION = "single_amount_with_direction"
    DEBIT_CREDIT_COLUMNS = "debit_credit_columns"
    INCOME_EXPENSE_COLUMNS = "income_expense_columns"
    SIGNED_AMOUNT = "signed_amount"


class PreviewStatus(StrEnum):
    NEEDS_CONFIRMATION = "needs_confirmation"
    AUTO_CONFIRMED = "auto_confirmed"
    MANUALLY_CONFIRMED = "manually_confirmed"
    CONFLICT = "conflict"
    PARSE_FAILED = "parse_failed"
    IGNORED = "ignored"


class ExceptionCode(StrEnum):
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_DATE = "INVALID_DATE"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    UNKNOWN_DIRECTION = "UNKNOWN_DIRECTION"
    AMOUNT_DIRECTION_MISMATCH = "AMOUNT_DIRECTION_MISMATCH"
    RULE_CONFLICT = "RULE_CONFLICT"
    NO_RULE_MATCH = "NO_RULE_MATCH"
    DUPLICATE_IN_BATCH = "DUPLICATE_IN_BATCH"
    DUPLICATE_HISTORY = "DUPLICATE_HISTORY"
    BALANCE_DISCONTINUITY = "BALANCE_DISCONTINUITY"
    TEMPLATE_NOT_MATCHED = "TEMPLATE_NOT_MATCHED"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
```

- [ ] **Step 4: Implement standard transaction schema**

Create `backend/app/schemas/standard.py` with:

```python
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import TransactionDirection


class StandardBankTransaction(BaseModel):
    transaction_date: str
    posting_date: str | None = None
    bank_account_id: str
    currency: str = "CNY"
    direction: TransactionDirection
    debit_amount: Decimal | None = None
    credit_amount: Decimal | None = None
    net_amount: Decimal
    balance: Decimal | None = None
    counterparty_name: str | None = None
    counterparty_account_no: str | None = None
    counterparty_bank_name: str | None = None
    summary: str | None = None
    purpose: str | None = None
    transaction_type: str | None = None
    bank_transaction_id: str | None = None
    receipt_no: str | None = None
    source_file_id: str
    source_sheet_name: str
    source_row_index: int = Field(ge=1)
    raw_row: dict[str, Any]
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
cd backend && pytest tests/unit/test_parser_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/core backend/app/schemas backend/tests/unit/test_parser_service.py
git commit -m "feat: add core financial schemas"
```

---

## Task 3: Add Database Models and Alembic Migration

**Files:**

- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/models/*.py`
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/0001_initial_schema.py`
- Test: `backend/tests/unit/test_template_service.py`

- [ ] **Step 1: Write immutable version model test**

Create `backend/tests/unit/test_template_service.py` with:

```python
from app.models.template import BankTemplateVersion


def test_bank_template_version_has_versioned_parser_config() -> None:
    version = BankTemplateVersion(
        bank_template_id="template-1",
        version_no=1,
        file_type="csv",
        sheet_selector_json={"mode": "first"},
        header_row_index=1,
        data_start_row_index=2,
        field_aliases_json={"交易日期": "transaction_date"},
        date_formats_json=["YYYY-MM-DD"],
        amount_mode="income_expense_columns",
        amount_config_json={"income": "收入", "expense": "支出"},
        unique_key_config_json={"fields": ["流水号"]},
        sample_file_id="file-1",
        created_by="user-1",
    )

    assert version.version_no == 1
    assert version.amount_config_json["income"] == "收入"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/unit/test_template_service.py -q
```

Expected: FAIL because ORM models do not exist.

- [ ] **Step 3: Implement database base and session**

Create `backend/app/db/base.py` with:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

Create `backend/app/db/session.py` with:

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Implement template ORM model used by test**

Create `backend/app/models/template.py` with:

```python
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BankTemplateVersion(Base):
    __tablename__ = "bank_template_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bank_template_id: Mapped[str] = mapped_column(String, ForeignKey("bank_templates.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    file_type: Mapped[str] = mapped_column(String)
    sheet_selector_json: Mapped[dict] = mapped_column(JSONB)
    header_row_index: Mapped[int] = mapped_column(Integer)
    data_start_row_index: Mapped[int] = mapped_column(Integer)
    field_aliases_json: Mapped[dict] = mapped_column(JSONB)
    date_formats_json: Mapped[list] = mapped_column(JSONB)
    amount_mode: Mapped[str] = mapped_column(String)
    amount_config_json: Mapped[dict] = mapped_column(JSONB)
    unique_key_config_json: Mapped[dict] = mapped_column(JSONB)
    sample_file_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
```

In the same file, add `BankTemplate`, `CompanyJournalTemplate`, and `CompanyJournalTemplateVersion`. Parent tables hold the editable identity fields and status. Version tables hold immutable parser/export configuration and a monotonically increasing `version_no`.

- [ ] **Step 5: Implement the rest of the ORM models**

Create `backend/app/models/user.py`, `company.py`, `file.py`, `mapping.py`, `rule.py`, `conversion.py`, and `audit.py` with one SQLAlchemy class per table. Use these table names exactly:

```text
users
roles
companies
bank_accounts
source_files
bank_templates
company_journal_templates
company_journal_template_versions
mapping_profiles
mapping_profile_versions
rules
rule_versions
conversion_runs
conversion_run_files
conversion_run_rule_versions
bank_transactions
journal_preview_rows
manual_adjustments
confirmations
exports
audit_logs
```

Use `String` UUID primary keys for MVP. Use PostgreSQL `JSONB` for all `*_json` columns. Use `Numeric(18, 2)` for money columns. Add `created_at` and `updated_at` where the technical design includes them.

- [ ] **Step 6: Add Alembic configuration and initial migration**

Create `backend/alembic.ini`, `backend/migrations/env.py`, and `backend/migrations/script.py.mako` using Alembic defaults, with `target_metadata = Base.metadata`.

Create `backend/migrations/versions/0001_initial_schema.py` with `upgrade()` creating all tables listed in Step 5 and `downgrade()` dropping them in reverse dependency order.

- [ ] **Step 7: Run model test**

Run:

```bash
cd backend && pytest tests/unit/test_template_service.py -q
```

Expected: PASS.

- [ ] **Step 8: Run migration on local PostgreSQL**

Run:

```bash
docker compose up -d postgres
cd backend && alembic upgrade head
```

Expected: migration completes and creates all MVP tables.

- [ ] **Step 9: Commit**

Run:

```bash
git add backend/app/db backend/app/models backend/alembic.ini backend/migrations backend/tests/unit/test_template_service.py
git commit -m "feat: add initial database schema"
```

---

## Task 4: Implement File Storage and Upload Metadata

**Files:**

- Create: `backend/app/services/file_service.py`
- Create: `backend/app/schemas/file.py`
- Create: `backend/app/api/routes/files.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_conversion_api.py`

- [ ] **Step 1: Write upload API test**

Create `backend/tests/integration/test_conversion_api.py` with:

```python
from pathlib import Path


def test_upload_csv_file_returns_file_metadata(client) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv"
    response = client.post(
        "/api/files/upload",
        files={"file": ("bank_statement_basic.csv", fixture.read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["original_filename"] == "bank_statement_basic.csv"
    assert payload["file_type"] == "csv"
    assert len(payload["sha256"]) == 64
```

- [ ] **Step 2: Add CSV fixture**

Create `backend/tests/fixtures/bank_statement_basic.csv` with:

```csv
交易日期,入账日期,收入,支出,余额,对方户名,对方账号,摘要,用途,流水号
2026-06-01,2026-06-01,12000.00,,98000.00,某客户有限公司,6222000000000000,货款,6月服务费,TXN001
2026-06-02,2026-06-02,,3000.00,95000.00,某供应商有限公司,6222111111111111,采购款,办公用品,TXN002
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/integration/test_conversion_api.py::test_upload_csv_file_returns_file_metadata -q
```

Expected: FAIL because upload route does not exist.

- [ ] **Step 4: Implement file schema and service**

Create `backend/app/schemas/file.py` with:

```python
from pydantic import BaseModel


class UploadedFileResponse(BaseModel):
    id: str
    company_id: str
    uploaded_by: str
    original_filename: str
    file_type: str
    file_size: int
    sha256: str
    storage_key: str
    status: str
```

Create `backend/app/services/file_service.py` with functions:

```python
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from app.core.config import get_settings


def detect_file_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix not in {"csv", "xlsx", "xls"}:
        raise ValueError(f"Unsupported file type: {suffix}")
    return suffix


def save_uploaded_file(filename: str, content: bytes) -> dict[str, str | int]:
    settings = get_settings()
    file_id = str(uuid.uuid4())
    file_type = detect_file_type(filename)
    digest = hashlib.sha256(content).hexdigest()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    storage_key = f"{file_id}.{file_type}"
    (upload_dir / storage_key).write_bytes(content)
    return {
        "id": file_id,
        "original_filename": filename,
        "file_type": file_type,
        "file_size": len(content),
        "sha256": digest,
        "storage_key": storage_key,
        "status": "pending",
    }
```

- [ ] **Step 5: Implement upload route**

Create `backend/app/api/routes/files.py` with:

```python
from fastapi import APIRouter, File, Form, UploadFile

from app.schemas.file import UploadedFileResponse
from app.services.file_service import save_uploaded_file

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload", response_model=UploadedFileResponse)
async def upload_file(
    company_id: str = Form(...),
    uploaded_by: str = Form(...),
    file: UploadFile = File(...),
) -> UploadedFileResponse:
    content = await file.read()
    saved = save_uploaded_file(file.filename or "upload", content)
    return UploadedFileResponse(company_id=company_id, uploaded_by=uploaded_by, **saved)
```

Modify `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api.routes import files

app = FastAPI(title="FA Tools API", version="0.1.0")
app.include_router(files.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Run upload API test**

Run:

```bash
cd backend && pytest tests/integration/test_conversion_api.py::test_upload_csv_file_returns_file_metadata -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/app/services/file_service.py backend/app/schemas/file.py backend/app/api backend/app/main.py backend/tests
git commit -m "feat: add source file upload"
```

---

## Task 5: Implement CSV/XLSX Parsing and Header Detection

**Files:**

- Modify: `backend/app/services/parser_service.py`
- Modify: `backend/tests/unit/test_parser_service.py`
- Create: `backend/tests/fixtures/bank_statement_basic.xlsx`

- [ ] **Step 1: Extend parser tests**

Append to `backend/tests/unit/test_parser_service.py`:

```python
from pathlib import Path

from app.core.enums import AmountMode, TransactionDirection
from app.services.parser_service import (
    BankTemplateParseConfig,
    detect_header_row,
    parse_bank_statement,
)


def test_detect_header_row_from_csv_preview() -> None:
    rows = [
        ["中国银行交易流水"],
        ["交易日期", "入账日期", "收入", "支出", "余额", "对方户名", "摘要"],
        ["2026-06-01", "2026-06-01", "12000.00", "", "98000.00", "某客户有限公司", "货款"],
    ]

    assert detect_header_row(rows) == 1


def test_parse_csv_statement_to_standard_transactions() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv"
    config = BankTemplateParseConfig(
        bank_account_id="bank-account-1",
        source_file_id="file-1",
        file_type="csv",
        sheet_name="Sheet1",
        header_row_index=0,
        data_start_row_index=1,
        field_aliases={
            "交易日期": "transaction_date",
            "入账日期": "posting_date",
            "收入": "income_amount",
            "支出": "expense_amount",
            "余额": "balance",
            "对方户名": "counterparty_name",
            "对方账号": "counterparty_account_no",
            "摘要": "summary",
            "用途": "purpose",
            "流水号": "bank_transaction_id",
        },
        amount_mode=AmountMode.INCOME_EXPENSE_COLUMNS,
        amount_config={"income": "income_amount", "expense": "expense_amount"},
        date_formats=["%Y-%m-%d"],
    )

    transactions = parse_bank_statement(fixture, config)

    assert len(transactions) == 2
    assert transactions[0].direction == TransactionDirection.CREDIT
    assert transactions[0].net_amount == Decimal("12000.00")
    assert transactions[1].direction == TransactionDirection.DEBIT
    assert transactions[1].net_amount == Decimal("-3000.00")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && pytest tests/unit/test_parser_service.py -q
```

Expected: FAIL because `parser_service` is not implemented.

- [ ] **Step 3: Implement parser service**

Create `backend/app/services/parser_service.py` with:

```python
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

from app.core.enums import AmountMode, TransactionDirection
from app.schemas.standard import StandardBankTransaction


HEADER_KEYWORDS = {
    "交易日期",
    "入账日期",
    "收入",
    "支出",
    "借方",
    "贷方",
    "金额",
    "余额",
    "对方户名",
    "对方账号",
    "摘要",
    "用途",
    "流水号",
}


@dataclass(frozen=True)
class BankTemplateParseConfig:
    bank_account_id: str
    source_file_id: str
    file_type: str
    sheet_name: str
    header_row_index: int
    data_start_row_index: int
    field_aliases: dict[str, str]
    amount_mode: AmountMode
    amount_config: dict[str, str]
    date_formats: list[str]
    currency: str = "CNY"


def detect_header_row(rows: list[list[object]], scan_limit: int = 30) -> int:
    best_index = 0
    best_score = -1
    for index, row in enumerate(rows[:scan_limit]):
        values = [str(cell).strip() for cell in row if str(cell).strip()]
        score = sum(1 for value in values if value in HEADER_KEYWORDS)
        if score > best_score:
            best_index = index
            best_score = score
    return best_index


def parse_bank_statement(path: Path, config: BankTemplateParseConfig) -> list[StandardBankTransaction]:
    rows = _read_rows(path, config.file_type)
    header = [str(cell).strip() for cell in rows[config.header_row_index]]
    transactions: list[StandardBankTransaction] = []
    for row_number, row in enumerate(rows[config.data_start_row_index :], start=config.data_start_row_index + 1):
        raw = {header[index]: row[index] if index < len(row) else "" for index in range(len(header))}
        normalized = {
            config.field_aliases[key]: value
            for key, value in raw.items()
            if key in config.field_aliases
        }
        direction, debit_amount, credit_amount, net_amount = _parse_amounts(normalized, config)
        transaction_date = _parse_date(str(normalized.get("transaction_date", "")), config.date_formats)
        posting_value = normalized.get("posting_date")
        posting_date = _parse_date(str(posting_value), config.date_formats) if posting_value else transaction_date
        transactions.append(
            StandardBankTransaction(
                transaction_date=transaction_date,
                posting_date=posting_date,
                bank_account_id=config.bank_account_id,
                currency=config.currency,
                direction=direction,
                debit_amount=debit_amount,
                credit_amount=credit_amount,
                net_amount=net_amount,
                balance=_decimal_or_none(normalized.get("balance")),
                counterparty_name=_text_or_none(normalized.get("counterparty_name")),
                counterparty_account_no=_text_or_none(normalized.get("counterparty_account_no")),
                counterparty_bank_name=_text_or_none(normalized.get("counterparty_bank_name")),
                summary=_text_or_none(normalized.get("summary")),
                purpose=_text_or_none(normalized.get("purpose")),
                transaction_type=_text_or_none(normalized.get("transaction_type")),
                bank_transaction_id=_text_or_none(normalized.get("bank_transaction_id")),
                receipt_no=_text_or_none(normalized.get("receipt_no")),
                source_file_id=config.source_file_id,
                source_sheet_name=config.sheet_name,
                source_row_index=row_number,
                raw_row=raw,
            )
        )
    return transactions


def _read_rows(path: Path, file_type: str) -> list[list[object]]:
    if file_type == "csv":
        with path.open("r", newline="", encoding="utf-8-sig") as file:
            return [row for row in csv.reader(file)]
    if file_type in {"xlsx", "xls"}:
        workbook = load_workbook(path, data_only=True, read_only=True)
        sheet = workbook.active
        return [[cell for cell in row] for row in sheet.iter_rows(values_only=True)]
    raise ValueError(f"Unsupported file type: {file_type}")


def _parse_amounts(
    row: dict[str, object],
    config: BankTemplateParseConfig,
) -> tuple[TransactionDirection, Decimal | None, Decimal | None, Decimal]:
    if config.amount_mode == AmountMode.INCOME_EXPENSE_COLUMNS:
        income = _decimal_or_none(row.get(config.amount_config["income"]))
        expense = _decimal_or_none(row.get(config.amount_config["expense"]))
        if income is not None and income != Decimal("0"):
            return TransactionDirection.CREDIT, None, income, income
        if expense is not None and expense != Decimal("0"):
            return TransactionDirection.DEBIT, expense, None, -expense
    raise ValueError("Unable to determine transaction amount and direction")


def _parse_date(value: str, formats: list[str]) -> str:
    stripped = value.strip()
    for date_format in formats:
        try:
            return datetime.strptime(stripped, date_format).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value}")


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if text == "":
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount: {value}") from exc


def _text_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
```

- [ ] **Step 4: Run parser unit tests**

Run:

```bash
cd backend && pytest tests/unit/test_parser_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Add XLSX fixture generation test**

Create `backend/tests/fixtures/bank_statement_basic.xlsx` by opening the CSV contents in a spreadsheet tool or by a short one-time script before committing. Verify the XLSX parser by adding a test that calls `parse_bank_statement` with `file_type="xlsx"` and expects the same two transactions as the CSV test.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/services/parser_service.py backend/tests/unit/test_parser_service.py backend/tests/fixtures
git commit -m "feat: parse bank statement files"
```

---

## Task 6: Implement Mapping Engine

**Files:**

- Create: `backend/app/services/mapping_service.py`
- Modify: `backend/tests/unit/test_mapping_service.py`

- [ ] **Step 1: Write mapping tests**

Create `backend/tests/unit/test_mapping_service.py` with:

```python
from decimal import Decimal

from app.core.enums import TransactionDirection
from app.schemas.standard import StandardBankTransaction
from app.services.mapping_service import apply_mappings


def test_apply_direct_fixed_and_concat_mappings() -> None:
    transaction = StandardBankTransaction(
        transaction_date="2026-06-01",
        posting_date="2026-06-01",
        bank_account_id="bank-account-1",
        currency="CNY",
        direction=TransactionDirection.CREDIT,
        debit_amount=None,
        credit_amount=Decimal("12000.00"),
        net_amount=Decimal("12000.00"),
        balance=Decimal("98000.00"),
        counterparty_name="某客户有限公司",
        counterparty_account_no="6222000000000000",
        counterparty_bank_name=None,
        summary="货款",
        purpose="6月服务费",
        transaction_type="转账",
        bank_transaction_id="TXN001",
        receipt_no=None,
        source_file_id="file-1",
        source_sheet_name="Sheet1",
        source_row_index=2,
        raw_row={},
    )
    mappings = [
        {"target": "日期", "type": "field", "source": "transaction_date"},
        {"target": "币种", "type": "fixed", "value": "人民币"},
        {"target": "备注", "type": "concat", "sources": ["summary", "purpose"], "separator": " - "},
    ]

    output = apply_mappings(transaction, mappings, rule_outputs={})

    assert output == {"日期": "2026-06-01", "币种": "人民币", "备注": "货款 - 6月服务费"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/unit/test_mapping_service.py -q
```

Expected: FAIL because mapping service does not exist.

- [ ] **Step 3: Implement mapping service**

Create `backend/app/services/mapping_service.py` with:

```python
from __future__ import annotations

from typing import Any

from app.schemas.standard import StandardBankTransaction


def apply_mappings(
    transaction: StandardBankTransaction,
    mappings: list[dict[str, Any]],
    rule_outputs: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    transaction_values = transaction.model_dump()
    for mapping in mappings:
        target = mapping["target"]
        mapping_type = mapping["type"]
        if mapping_type == "field":
            result[target] = transaction_values.get(mapping["source"])
        elif mapping_type == "fixed":
            result[target] = mapping.get("value")
        elif mapping_type == "rule_output":
            result[target] = rule_outputs.get(mapping["source"])
        elif mapping_type == "concat":
            separator = mapping.get("separator", "")
            values = [
                str(transaction_values.get(source) or "")
                for source in mapping.get("sources", [])
                if transaction_values.get(source) not in (None, "")
            ]
            result[target] = separator.join(values)
        elif mapping_type == "manual":
            result[target] = None
        else:
            raise ValueError(f"Unsupported mapping type: {mapping_type}")
    return result
```

- [ ] **Step 4: Run mapping tests**

Run:

```bash
cd backend && pytest tests/unit/test_mapping_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/services/mapping_service.py backend/tests/unit/test_mapping_service.py
git commit -m "feat: apply journal field mappings"
```

---

## Task 7: Implement Rule Engine

**Files:**

- Create: `backend/app/services/rule_service.py`
- Modify: `backend/tests/unit/test_rule_service.py`

- [ ] **Step 1: Write rule matching and conflict tests**

Create `backend/tests/unit/test_rule_service.py` with:

```python
from decimal import Decimal

from app.core.enums import ExceptionCode, TransactionDirection
from app.schemas.standard import StandardBankTransaction
from app.services.rule_service import apply_rules


def _transaction() -> StandardBankTransaction:
    return StandardBankTransaction(
        transaction_date="2026-06-01",
        posting_date="2026-06-01",
        bank_account_id="bank-account-1",
        currency="CNY",
        direction=TransactionDirection.CREDIT,
        debit_amount=None,
        credit_amount=Decimal("12000.00"),
        net_amount=Decimal("12000.00"),
        balance=Decimal("98000.00"),
        counterparty_name="某客户有限公司",
        counterparty_account_no="6222000000000000",
        counterparty_bank_name=None,
        summary="货款",
        purpose="6月服务费",
        transaction_type="转账",
        bank_transaction_id="TXN001",
        receipt_no=None,
        source_file_id="file-1",
        source_sheet_name="Sheet1",
        source_row_index=2,
        raw_row={},
    )


def test_apply_rules_returns_outputs_and_trace() -> None:
    rules = [
        {
            "id": "rule-1",
            "version_id": "rule-version-1",
            "priority": 10,
            "conditions": {
                "all": [
                    {"field": "direction", "op": "eq", "value": "credit"},
                    {"field": "summary", "op": "contains", "value": "货款"},
                ]
            },
            "actions": [
                {"field": "journal_summary", "value": "收到客户款项"},
                {"field": "account_subject", "value": "银行存款"},
            ],
            "allow_auto_confirm": False,
        }
    ]

    result = apply_rules(_transaction(), rules)

    assert result.outputs["journal_summary"] == "收到客户款项"
    assert result.outputs["account_subject"] == "银行存款"
    assert result.matched_rule_version_ids == ["rule-version-1"]
    assert result.exceptions == []


def test_apply_rules_marks_field_conflict() -> None:
    rules = [
        {
            "id": "rule-1",
            "version_id": "rule-version-1",
            "priority": 10,
            "conditions": {"all": [{"field": "summary", "op": "contains", "value": "货款"}]},
            "actions": [{"field": "account_subject", "value": "银行存款"}],
            "allow_auto_confirm": False,
        },
        {
            "id": "rule-2",
            "version_id": "rule-version-2",
            "priority": 20,
            "conditions": {"all": [{"field": "counterparty_name", "op": "contains", "value": "客户"}]},
            "actions": [{"field": "account_subject", "value": "应收账款"}],
            "allow_auto_confirm": False,
        },
    ]

    result = apply_rules(_transaction(), rules)

    assert ExceptionCode.RULE_CONFLICT in result.exceptions
    assert result.conflicts["account_subject"] == ["银行存款", "应收账款"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && pytest tests/unit/test_rule_service.py -q
```

Expected: FAIL because rule service does not exist.

- [ ] **Step 3: Implement rule service**

Create `backend/app/services/rule_service.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.core.enums import ExceptionCode
from app.schemas.standard import StandardBankTransaction


@dataclass
class RuleApplicationResult:
    outputs: dict[str, Any] = field(default_factory=dict)
    matched_rule_version_ids: list[str] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    exceptions: list[ExceptionCode] = field(default_factory=list)
    conflicts: dict[str, list[Any]] = field(default_factory=dict)
    all_matched_rules_allow_auto_confirm: bool = False


def apply_rules(
    transaction: StandardBankTransaction,
    rules: list[dict[str, Any]],
) -> RuleApplicationResult:
    result = RuleApplicationResult(all_matched_rules_allow_auto_confirm=False)
    matched_auto_flags: list[bool] = []
    for rule in sorted(rules, key=lambda item: item["priority"]):
        if not _matches(transaction, rule["conditions"]):
            continue
        result.matched_rule_version_ids.append(rule["version_id"])
        matched_auto_flags.append(bool(rule.get("allow_auto_confirm", False)))
        for action in rule["actions"]:
            field_name = action["field"]
            value = action["value"]
            if field_name in result.outputs and result.outputs[field_name] != value:
                values = result.conflicts.setdefault(field_name, [result.outputs[field_name]])
                if value not in values:
                    values.append(value)
                if ExceptionCode.RULE_CONFLICT not in result.exceptions:
                    result.exceptions.append(ExceptionCode.RULE_CONFLICT)
            else:
                result.outputs[field_name] = value
            result.trace.append(
                {
                    "rule_id": rule["id"],
                    "rule_version_id": rule["version_id"],
                    "field": field_name,
                    "value": value,
                }
            )
    result.all_matched_rules_allow_auto_confirm = bool(matched_auto_flags) and all(matched_auto_flags)
    return result


def _matches(transaction: StandardBankTransaction, conditions: dict[str, Any]) -> bool:
    values = transaction.model_dump()
    return all(_match_condition(values, condition) for condition in conditions.get("all", []))


def _match_condition(values: dict[str, Any], condition: dict[str, Any]) -> bool:
    actual = values.get(condition["field"])
    expected = condition.get("value")
    op = condition["op"]
    if hasattr(actual, "value"):
        actual = actual.value
    if op == "eq":
        return actual == expected
    if op == "contains":
        return expected in str(actual or "")
    if op == "contains_any":
        return any(item in str(actual or "") for item in expected)
    if op == "not_contains":
        return expected not in str(actual or "")
    if op == "gte":
        return Decimal(str(actual)) >= Decimal(str(expected))
    if op == "lte":
        return Decimal(str(actual)) <= Decimal(str(expected))
    raise ValueError(f"Unsupported rule operator: {op}")
```

- [ ] **Step 4: Run rule tests**

Run:

```bash
cd backend && pytest tests/unit/test_rule_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/services/rule_service.py backend/tests/unit/test_rule_service.py
git commit -m "feat: apply journal rules"
```

---

## Task 8: Implement Conversion Service and Preview Row Status

**Files:**

- Create: `backend/app/services/conversion_service.py`
- Create: `backend/app/schemas/conversion.py`
- Modify: `backend/tests/unit/test_mapping_service.py`
- Modify: `backend/tests/unit/test_rule_service.py`

- [ ] **Step 1: Write conversion service test**

Create or append `backend/tests/unit/test_conversion_service.py` with:

```python
from decimal import Decimal

from app.core.enums import ExceptionCode, PreviewStatus, TransactionDirection
from app.schemas.standard import StandardBankTransaction
from app.services.conversion_service import build_preview_row


def test_build_preview_row_requires_confirmation_when_required_field_missing() -> None:
    transaction = StandardBankTransaction(
        transaction_date="2026-06-01",
        posting_date="2026-06-01",
        bank_account_id="bank-account-1",
        currency="CNY",
        direction=TransactionDirection.CREDIT,
        debit_amount=None,
        credit_amount=Decimal("12000.00"),
        net_amount=Decimal("12000.00"),
        balance=Decimal("98000.00"),
        counterparty_name="某客户有限公司",
        counterparty_account_no="6222000000000000",
        counterparty_bank_name=None,
        summary="货款",
        purpose="6月服务费",
        transaction_type="转账",
        bank_transaction_id="TXN001",
        receipt_no=None,
        source_file_id="file-1",
        source_sheet_name="Sheet1",
        source_row_index=2,
        raw_row={},
    )

    row = build_preview_row(
        transaction=transaction,
        mappings=[{"target": "日期", "type": "field", "source": "transaction_date"}],
        rules=[],
        required_columns=["日期", "科目"],
        row_index=1,
    )

    assert row.status == PreviewStatus.NEEDS_CONFIRMATION
    assert ExceptionCode.MISSING_REQUIRED_FIELD in row.exception_codes
    assert row.output_values["日期"] == "2026-06-01"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/unit/test_conversion_service.py -q
```

Expected: FAIL because conversion service does not exist.

- [ ] **Step 3: Implement conversion schemas**

Create `backend/app/schemas/conversion.py` with:

```python
from typing import Any

from pydantic import BaseModel

from app.core.enums import ExceptionCode, PreviewStatus


class JournalPreviewRowData(BaseModel):
    row_index: int
    output_values: dict[str, Any]
    status: PreviewStatus
    exception_codes: list[ExceptionCode]
    matched_rule_version_ids: list[str]
    rule_trace: list[dict[str, Any]]
```

- [ ] **Step 4: Implement conversion service**

Create `backend/app/services/conversion_service.py` with:

```python
from __future__ import annotations

from typing import Any

from app.core.enums import ExceptionCode, PreviewStatus
from app.schemas.conversion import JournalPreviewRowData
from app.schemas.standard import StandardBankTransaction
from app.services.mapping_service import apply_mappings
from app.services.rule_service import apply_rules


def build_preview_row(
    transaction: StandardBankTransaction,
    mappings: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    required_columns: list[str],
    row_index: int,
) -> JournalPreviewRowData:
    rule_result = apply_rules(transaction, rules)
    output_values = apply_mappings(transaction, mappings, rule_result.outputs)
    exceptions = list(rule_result.exceptions)
    missing_required = [
        column for column in required_columns if output_values.get(column) in (None, "")
    ]
    if missing_required and ExceptionCode.MISSING_REQUIRED_FIELD not in exceptions:
        exceptions.append(ExceptionCode.MISSING_REQUIRED_FIELD)
    if not rule_result.matched_rule_version_ids and ExceptionCode.NO_RULE_MATCH not in exceptions:
        exceptions.append(ExceptionCode.NO_RULE_MATCH)
    status = _preview_status(exceptions, rule_result.all_matched_rules_allow_auto_confirm)
    return JournalPreviewRowData(
        row_index=row_index,
        output_values=output_values,
        status=status,
        exception_codes=exceptions,
        matched_rule_version_ids=rule_result.matched_rule_version_ids,
        rule_trace=rule_result.trace,
    )


def _preview_status(
    exceptions: list[ExceptionCode],
    all_matched_rules_allow_auto_confirm: bool,
) -> PreviewStatus:
    if ExceptionCode.RULE_CONFLICT in exceptions:
        return PreviewStatus.CONFLICT
    if ExceptionCode.MISSING_REQUIRED_FIELD in exceptions:
        return PreviewStatus.NEEDS_CONFIRMATION
    if ExceptionCode.NO_RULE_MATCH in exceptions:
        return PreviewStatus.NEEDS_CONFIRMATION
    if all_matched_rules_allow_auto_confirm:
        return PreviewStatus.AUTO_CONFIRMED
    return PreviewStatus.NEEDS_CONFIRMATION
```

- [ ] **Step 5: Run conversion tests**

Run:

```bash
cd backend && pytest tests/unit/test_conversion_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/schemas/conversion.py backend/app/services/conversion_service.py backend/tests/unit/test_conversion_service.py
git commit -m "feat: build conversion preview rows"
```

---

## Task 9: Add Template, Mapping, and Rule CRUD APIs

**Files:**

- Create: `backend/app/schemas/template.py`
- Create: `backend/app/schemas/mapping.py`
- Create: `backend/app/schemas/rule.py`
- Create: `backend/app/services/template_service.py`
- Create: `backend/app/api/routes/bank_templates.py`
- Create: `backend/app/api/routes/journal_templates.py`
- Create: `backend/app/api/routes/mapping_profiles.py`
- Create: `backend/app/api/routes/rules.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_conversion_api.py`

- [ ] **Step 1: Write API tests for creating versioned configuration**

Append to `backend/tests/integration/test_conversion_api.py`:

```python
def test_create_bank_template_version(client) -> None:
    response = client.post(
        "/api/bank-templates",
        json={
            "company_id": "company-1",
            "name": "中国银行 CSV",
            "bank_name": "中国银行",
            "bank_account_id": "bank-account-1",
            "version": {
                "file_type": "csv",
                "sheet_selector_json": {"mode": "first"},
                "header_row_index": 0,
                "data_start_row_index": 1,
                "field_aliases_json": {"交易日期": "transaction_date"},
                "date_formats_json": ["%Y-%m-%d"],
                "amount_mode": "income_expense_columns",
                "amount_config_json": {"income": "income_amount", "expense": "expense_amount"},
                "unique_key_config_json": {"fields": ["流水号"]},
                "sample_file_id": "file-1",
                "created_by": "user-1",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "中国银行 CSV"
    assert payload["latest_version"]["version_no"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/integration/test_conversion_api.py::test_create_bank_template_version -q
```

Expected: FAIL because route does not exist.

- [ ] **Step 3: Implement Pydantic schemas**

Create request and response schemas for:

```text
BankTemplateCreate
BankTemplateResponse
CompanyJournalTemplateCreate
CompanyJournalTemplateResponse
MappingProfileCreate
MappingProfileResponse
RuleCreate
RuleResponse
```

Use field names from `docs/technical-design-bank-statement-journal.md` exactly, including `*_json` suffixes where the database stores raw JSON.

- [ ] **Step 4: Implement template service with in-memory fallback**

For MVP integration tests, implement a module-level in-memory store in `template_service.py` first. The functions must be:

```python
def create_bank_template(payload: BankTemplateCreate) -> BankTemplateResponse: ...
def list_bank_templates(company_id: str | None = None) -> list[BankTemplateResponse]: ...
def create_journal_template(payload: CompanyJournalTemplateCreate) -> CompanyJournalTemplateResponse: ...
def list_journal_templates(company_id: str | None = None) -> list[CompanyJournalTemplateResponse]: ...
```

After the route tests pass, replace the in-memory store with SQLAlchemy persistence in the same public functions.

- [ ] **Step 5: Implement routes and register them**

Create one APIRouter per resource. Register them in `backend/app/main.py`:

```python
from app.api.routes import (
    bank_templates,
    files,
    journal_templates,
    mapping_profiles,
    rules,
)

app.include_router(files.router)
app.include_router(bank_templates.router)
app.include_router(journal_templates.router)
app.include_router(mapping_profiles.router)
app.include_router(rules.router)
```

- [ ] **Step 6: Run configuration API tests**

Run:

```bash
cd backend && pytest tests/integration/test_conversion_api.py -q
```

Expected: existing upload test and new template test pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/app/schemas backend/app/services/template_service.py backend/app/api/routes backend/app/main.py backend/tests/integration/test_conversion_api.py
git commit -m "feat: manage versioned conversion configuration"
```

---

## Task 10: Add Conversion Run API

**Files:**

- Modify: `backend/app/api/routes/conversion_runs.py`
- Modify: `backend/app/services/conversion_service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_conversion_api.py`

- [ ] **Step 1: Write conversion run integration test**

Append to `backend/tests/integration/test_conversion_api.py`:

```python
def test_start_conversion_run_creates_preview_rows(client) -> None:
    upload = client.post(
        "/api/files/upload",
        files={"file": ("bank_statement_basic.csv", (Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv").read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    ).json()

    response = client.post(
        "/api/conversion-runs",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [upload["id"]],
            "bank_parse_config": {
                "file_type": "csv",
                "sheet_name": "Sheet1",
                "header_row_index": 0,
                "data_start_row_index": 1,
                "field_aliases": {
                    "交易日期": "transaction_date",
                    "入账日期": "posting_date",
                    "收入": "income_amount",
                    "支出": "expense_amount",
                    "余额": "balance",
                    "对方户名": "counterparty_name",
                    "对方账号": "counterparty_account_no",
                    "摘要": "summary",
                    "用途": "purpose",
                    "流水号": "bank_transaction_id"
                },
                "amount_mode": "income_expense_columns",
                "amount_config": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats": ["%Y-%m-%d"]
            },
            "mappings": [
                {"target": "日期", "type": "field", "source": "transaction_date"},
                {"target": "摘要", "type": "rule_output", "source": "journal_summary"},
                {"target": "科目", "type": "rule_output", "source": "account_subject"},
                {"target": "金额", "type": "field", "source": "net_amount"}
            ],
            "rules": [
                {
                    "id": "rule-1",
                    "version_id": "rule-version-1",
                    "priority": 10,
                    "conditions": {"all": [{"field": "summary", "op": "contains", "value": "货款"}]},
                    "actions": [
                        {"field": "journal_summary", "value": "收到客户款项"},
                        {"field": "account_subject", "value": "银行存款"}
                    ],
                    "allow_auto_confirm": False
                }
            ],
            "required_columns": ["日期", "摘要", "科目", "金额"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_rows"] == 2
    assert payload["preview_rows"][0]["output_values"]["科目"] == "银行存款"
    assert payload["preview_rows"][1]["status"] == "needs_confirmation"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/integration/test_conversion_api.py::test_start_conversion_run_creates_preview_rows -q
```

Expected: FAIL because conversion run route does not exist.

- [ ] **Step 3: Implement conversion run route**

Create `backend/app/api/routes/conversion_runs.py` with endpoint:

```text
POST /api/conversion-runs
```

The endpoint must:

1. Resolve uploaded files from the local upload directory.
2. Build `BankTemplateParseConfig` for each file.
3. Parse standard transactions.
4. Build preview rows using mappings, rules, and required columns.
5. Return a response containing `id`, `status`, `summary`, and `preview_rows`.

- [ ] **Step 4: Register conversion route**

Modify `backend/app/main.py` to include:

```python
from app.api.routes import conversion_runs

app.include_router(conversion_runs.router)
```

- [ ] **Step 5: Run conversion API test**

Run:

```bash
cd backend && pytest tests/integration/test_conversion_api.py::test_start_conversion_run_creates_preview_rows -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/api/routes/conversion_runs.py backend/app/services/conversion_service.py backend/app/main.py backend/tests/integration/test_conversion_api.py
git commit -m "feat: create conversion runs"
```

---

## Task 11: Add Manual Adjustment and Confirmation API

**Files:**

- Create: `backend/app/services/confirmation_service.py`
- Create: `backend/app/api/routes/preview_rows.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_conversion_api.py`

- [ ] **Step 1: Write confirmation test**

Append to `backend/tests/integration/test_conversion_api.py`:

```python
def test_confirm_preview_row_after_manual_adjustment(client) -> None:
    row_id = "preview-row-1"
    patch_response = client.patch(
        f"/api/preview-rows/{row_id}",
        json={
            "field_name": "科目",
            "new_value": "银行存款",
            "reason": "人工确认供应商付款科目",
            "adjusted_by": "user-1",
        },
    )

    assert patch_response.status_code == 200
    assert patch_response.json()["field_name"] == "科目"

    confirm_response = client.post(
        f"/api/preview-rows/{row_id}/confirm",
        json={"confirmed_by": "user-1", "comment": "已核对"},
    )

    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "manually_confirmed"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/integration/test_conversion_api.py::test_confirm_preview_row_after_manual_adjustment -q
```

Expected: FAIL because preview row routes do not exist.

- [ ] **Step 3: Implement confirmation service and routes**

Create `confirmation_service.py` with two functions:

```python
def record_manual_adjustment(row_id: str, field_name: str, new_value: str, reason: str, adjusted_by: str) -> dict: ...
def confirm_preview_row(row_id: str, confirmed_by: str, comment: str | None) -> dict: ...
```

For this task, keep an in-memory dictionary named `PREVIEW_ROW_STORE` in `confirmation_service.py` so API behavior is testable before database persistence is connected. Task 18 replaces this dictionary with writes to `manual_adjustments`, `confirmations`, and `journal_preview_rows`.

- [ ] **Step 4: Register preview row route**

Modify `backend/app/main.py` to include:

```python
from app.api.routes import preview_rows

app.include_router(preview_rows.router)
```

- [ ] **Step 5: Run confirmation test**

Run:

```bash
cd backend && pytest tests/integration/test_conversion_api.py::test_confirm_preview_row_after_manual_adjustment -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/services/confirmation_service.py backend/app/api/routes/preview_rows.py backend/app/main.py backend/tests/integration/test_conversion_api.py
git commit -m "feat: confirm journal preview rows"
```

---

## Task 12: Implement Export Service and Download API

**Files:**

- Create: `backend/app/services/export_service.py`
- Create: `backend/app/api/routes/exports.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/unit/test_export_service.py`
- Test: `backend/tests/integration/test_export_api.py`

- [ ] **Step 1: Write export unit test**

Create `backend/tests/unit/test_export_service.py` with:

```python
from pathlib import Path

from app.services.export_service import export_preview_rows_to_csv


def test_export_preview_rows_to_csv(tmp_path: Path) -> None:
    rows = [
        {"日期": "2026-06-01", "摘要": "收到客户款项", "科目": "银行存款", "金额": "12000.00"},
        {"日期": "2026-06-02", "摘要": "支付采购款", "科目": "管理费用", "金额": "-3000.00"},
    ]

    output = export_preview_rows_to_csv(
        rows=rows,
        columns=["日期", "摘要", "科目", "金额"],
        output_dir=tmp_path,
        filename="journal.csv",
    )

    assert output.read_text(encoding="utf-8-sig").splitlines()[0] == "日期,摘要,科目,金额"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/unit/test_export_service.py -q
```

Expected: FAIL because export service does not exist.

- [ ] **Step 3: Implement CSV export**

Create `backend/app/services/export_service.py` with:

```python
from __future__ import annotations

import csv
from pathlib import Path


def export_preview_rows_to_csv(
    rows: list[dict[str, object]],
    columns: list[str],
    output_dir: Path,
    filename: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path
```

- [ ] **Step 4: Add XLSX export**

Extend `export_service.py` with:

```python
from openpyxl import Workbook


def export_preview_rows_to_xlsx(
    rows: list[dict[str, object]],
    columns: list[str],
    output_dir: Path,
    filename: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(columns)
    for row in rows:
        sheet.append([row.get(column) for column in columns])
    workbook.save(path)
    return path
```

- [ ] **Step 5: Write export API test**

Create `backend/tests/integration/test_export_api.py` with:

```python
def test_export_preview_rows_returns_download_metadata(client) -> None:
    response = client.post(
        "/api/conversion-runs/run-1/exports",
        json={
            "file_type": "csv",
            "columns": ["日期", "摘要", "科目", "金额"],
            "rows": [
                {"日期": "2026-06-01", "摘要": "收到客户款项", "科目": "银行存款", "金额": "12000.00"}
            ],
            "exported_by": "user-1",
            "only_confirmed": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["file_type"] == "csv"
    assert payload["row_count"] == 1
    assert payload["download_url"].startswith("/api/exports/")
```

- [ ] **Step 6: Implement export route**

Create `backend/app/api/routes/exports.py` with:

```text
POST /api/conversion-runs/{run_id}/exports
GET /api/exports/{export_id}/download
```

The POST endpoint writes the export file and returns metadata with `download_url`. The GET endpoint returns `FileResponse`.

- [ ] **Step 7: Run export tests**

Run:

```bash
cd backend && pytest tests/unit/test_export_service.py tests/integration/test_export_api.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add backend/app/services/export_service.py backend/app/api/routes/exports.py backend/app/main.py backend/tests/unit/test_export_service.py backend/tests/integration/test_export_api.py
git commit -m "feat: export journal files"
```

---

## Task 13: Add Audit Logging Boundary

**Files:**

- Create: `backend/app/services/audit_service.py`
- Create: `backend/app/api/routes/audit.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/unit/test_audit_service.py`

- [ ] **Step 1: Write audit service test**

Create `backend/tests/unit/test_audit_service.py` with:

```python
from app.services.audit_service import build_audit_event


def test_build_audit_event_contains_before_and_after_snapshots() -> None:
    event = build_audit_event(
        company_id="company-1",
        actor_id="user-1",
        action="template.version.created",
        entity_type="bank_template_version",
        entity_id="version-1",
        before=None,
        after={"version_no": 1},
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert event["action"] == "template.version.created"
    assert event["after_json"] == {"version_no": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/unit/test_audit_service.py -q
```

Expected: FAIL because audit service does not exist.

- [ ] **Step 3: Implement audit service**

Create `backend/app/services/audit_service.py` with:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def build_audit_event(
    company_id: str,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    ip_address: str | None,
    user_agent: str | None,
) -> dict[str, Any]:
    return {
        "company_id": company_id,
        "actor_id": actor_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "before_json": before,
        "after_json": after,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "created_at": datetime.now(UTC).isoformat(),
    }
```

- [ ] **Step 4: Add audit read route**

Create `backend/app/api/routes/audit.py` with `GET /api/audit-logs`. For MVP, it can return persisted audit events after SQLAlchemy wiring is complete or an empty list before the first event is recorded.

- [ ] **Step 5: Run audit tests**

Run:

```bash
cd backend && pytest tests/unit/test_audit_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/services/audit_service.py backend/app/api/routes/audit.py backend/app/main.py backend/tests/unit/test_audit_service.py
git commit -m "feat: add audit event boundary"
```

---

## Task 14: Scaffold Frontend App

**Files:**

- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/components/AppShell.tsx`
- Create: `frontend/src/api/client.ts`
- Test: `frontend/tests/app.spec.ts`

- [ ] **Step 1: Create package manifest**

Create `frontend/package.json` with:

```json
{
  "name": "fa-tools-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "e2e": "playwright test"
  },
  "dependencies": {
    "@ant-design/icons": "^5.5.1",
    "antd": "^5.20.6",
    "axios": "^1.7.7",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.1"
  },
  "devDependencies": {
    "@playwright/test": "^1.46.1",
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.5.4",
    "vite": "^5.4.2",
    "vitest": "^2.0.5"
  }
}
```

- [ ] **Step 2: Implement basic shell**

Create `frontend/src/components/AppShell.tsx` with:

```tsx
import { AuditOutlined, FileTextOutlined, SettingOutlined, UploadOutlined } from '@ant-design/icons';
import { Layout, Menu, Typography } from 'antd';
import type { ReactNode } from 'react';

const { Header, Sider, Content } = Layout;

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <Layout className="app-shell">
      <Sider width={232} className="app-sider">
        <Typography.Title level={4} className="app-title">FA Tools</Typography.Title>
        <Menu
          theme="dark"
          mode="inline"
          defaultSelectedKeys={['upload']}
          items={[
            { key: 'upload', icon: <UploadOutlined />, label: '流水上传' },
            { key: 'runs', icon: <FileTextOutlined />, label: '处理批次' },
            { key: 'templates', icon: <SettingOutlined />, label: '模板规则' },
            { key: 'audit', icon: <AuditOutlined />, label: '审计日志' }
          ]}
        />
      </Sider>
      <Layout>
        <Header className="app-header">银行流水转日记账</Header>
        <Content className="app-content">{children}</Content>
      </Layout>
    </Layout>
  );
}
```

Create `frontend/src/App.tsx` with:

```tsx
import { Button, Card, Space, Typography } from 'antd';
import { AppShell } from './components/AppShell';

export default function App() {
  return (
    <AppShell>
      <Card className="work-card">
        <Space direction="vertical" size={16}>
          <Typography.Title level={3}>流水上传</Typography.Title>
          <Typography.Text>上传银行流水，生成公司日记账预览。</Typography.Text>
          <Button type="primary">选择文件</Button>
        </Space>
      </Card>
    </AppShell>
  );
}
```

Create `frontend/src/main.tsx` with:

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 3: Add frontend styling**

Create `frontend/src/styles.css` with:

```css
html,
body,
#root {
  width: 100%;
  height: 100%;
  margin: 0;
}

.app-shell {
  min-height: 100vh;
}

.app-sider {
  background: #182230;
}

.app-title {
  color: #fff !important;
  margin: 20px 20px 16px !important;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 600;
}

.app-content {
  padding: 24px;
  background: #f6f7f9;
}

.work-card {
  border-radius: 8px;
}
```

- [ ] **Step 4: Build frontend**

Run:

```bash
cd frontend && npm install && npm run build
```

Expected: build succeeds.

- [ ] **Step 5: Commit**

Run:

```bash
git add frontend
git commit -m "feat: scaffold frontend shell"
```

---

## Task 15: Build Frontend Upload and Preview Flow

**Files:**

- Create: `frontend/src/types/conversion.ts`
- Create: `frontend/src/api/files.ts`
- Create: `frontend/src/api/conversionRuns.ts`
- Create: `frontend/src/components/ExceptionTag.tsx`
- Create: `frontend/src/components/StatusTag.tsx`
- Create: `frontend/src/pages/UploadPage.tsx`
- Create: `frontend/src/pages/ConversionRunDetailPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add API client functions**

Create `frontend/src/api/client.ts` with:

```ts
import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
});
```

Create `frontend/src/api/files.ts` with:

```ts
import { apiClient } from './client';

export async function uploadBankStatement(file: File) {
  const form = new FormData();
  form.append('company_id', 'company-1');
  form.append('uploaded_by', 'user-1');
  form.append('file', file);
  const response = await apiClient.post('/api/files/upload', form);
  return response.data;
}
```

Create `frontend/src/api/conversionRuns.ts` with:

```ts
import { apiClient } from './client';

export async function createConversionRun(sourceFileIds: string[]) {
  const response = await apiClient.post('/api/conversion-runs', {
    company_id: 'company-1',
    bank_account_id: 'bank-account-1',
    source_file_ids: sourceFileIds,
    bank_parse_config: {
      file_type: 'csv',
      sheet_name: 'Sheet1',
      header_row_index: 0,
      data_start_row_index: 1,
      field_aliases: {
        交易日期: 'transaction_date',
        入账日期: 'posting_date',
        收入: 'income_amount',
        支出: 'expense_amount',
        余额: 'balance',
        对方户名: 'counterparty_name',
        对方账号: 'counterparty_account_no',
        摘要: 'summary',
        用途: 'purpose',
        流水号: 'bank_transaction_id'
      },
      amount_mode: 'income_expense_columns',
      amount_config: { income: 'income_amount', expense: 'expense_amount' },
      date_formats: ['%Y-%m-%d']
    },
    mappings: [
      { target: '日期', type: 'field', source: 'transaction_date' },
      { target: '摘要', type: 'rule_output', source: 'journal_summary' },
      { target: '科目', type: 'rule_output', source: 'account_subject' },
      { target: '金额', type: 'field', source: 'net_amount' }
    ],
    rules: [
      {
        id: 'rule-1',
        version_id: 'rule-version-1',
        priority: 10,
        conditions: { all: [{ field: 'summary', op: 'contains', value: '货款' }] },
        actions: [
          { field: 'journal_summary', value: '收到客户款项' },
          { field: 'account_subject', value: '银行存款' }
        ],
        allow_auto_confirm: false
      }
    ],
    required_columns: ['日期', '摘要', '科目', '金额']
  });
  return response.data;
}
```

- [ ] **Step 2: Implement upload page**

Create `frontend/src/pages/UploadPage.tsx` with an Ant Design `Upload.Dragger`, a primary action button, and a summary panel showing uploaded file names and conversion run summary.

The button flow must:

1. Upload selected files with `uploadBankStatement`.
2. Call `createConversionRun` with returned file IDs.
3. Render preview rows in `ConversionRunDetailPage`.

- [ ] **Step 3: Implement preview detail page**

Create `frontend/src/pages/ConversionRunDetailPage.tsx` with an Ant Design `Table` showing:

```text
日期
摘要
科目
金额
status
exception_codes
```

Use `StatusTag` for status and `ExceptionTag` for each exception code.

- [ ] **Step 4: Wire App to upload page**

Modify `frontend/src/App.tsx` to render `UploadPage` inside `AppShell`.

- [ ] **Step 5: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: build succeeds.

- [ ] **Step 6: Commit**

Run:

```bash
git add frontend/src
git commit -m "feat: add upload and preview UI"
```

---

## Task 16: Add Template, Mapping, Rule, Batch, and Audit Pages

**Files:**

- Create: `frontend/src/pages/BankTemplatePage.tsx`
- Create: `frontend/src/pages/JournalTemplatePage.tsx`
- Create: `frontend/src/pages/MappingProfilePage.tsx`
- Create: `frontend/src/pages/RulePage.tsx`
- Create: `frontend/src/pages/ConversionRunListPage.tsx`
- Create: `frontend/src/pages/AuditLogPage.tsx`
- Create: `frontend/src/components/VersionBadge.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Implement VersionBadge**

Create `frontend/src/components/VersionBadge.tsx`:

```tsx
import { Tag } from 'antd';

export function VersionBadge({ version }: { version: number | string }) {
  return <Tag color="blue">v{version}</Tag>;
}
```

- [ ] **Step 2: Implement management pages as functional MVP screens**

Each page must render a table with realistic columns and a drawer or modal for create/edit actions:

```text
BankTemplatePage: name, bank_name, bank_account_id, status, latest_version
JournalTemplatePage: name, status, latest_version
MappingProfilePage: name, bank_template, journal_template, status, latest_version
RulePage: name, priority, scope, status, allow_auto_confirm, latest_version
ConversionRunListPage: id, company, bank_account, status, total_rows, exception_rows, created_at
AuditLogPage: action, entity_type, entity_id, actor_id, created_at
```

Use local component state for these management pages in this task. Task 18 provides persistent backend records; after Task 18, replace local arrays with API calls through `frontend/src/api/templates.ts`, `frontend/src/api/rules.ts`, and `frontend/src/api/conversionRuns.ts`.

- [ ] **Step 3: Wire navigation**

Modify `AppShell` so menu selection changes the visible page in `App.tsx`.

- [ ] **Step 4: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: build succeeds.

- [ ] **Step 5: Commit**

Run:

```bash
git add frontend/src
git commit -m "feat: add configuration management UI"
```

---

## Task 17: Add End-to-End Sample Flow Test

**Files:**

- Create: `frontend/tests/conversion-flow.spec.ts`
- Create: `frontend/playwright.config.ts`
- Modify: `README.md`

- [ ] **Step 1: Add Playwright config**

Create `frontend/playwright.config.ts` with:

```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  use: {
    baseURL: 'http://localhost:5173'
  },
  webServer: {
    command: 'npm run dev -- --port 5173',
    url: 'http://localhost:5173',
    reuseExistingServer: true
  }
});
```

- [ ] **Step 2: Write smoke test**

Create `frontend/tests/conversion-flow.spec.ts` with:

```ts
import { expect, test } from '@playwright/test';

test('shows bank statement journal workspace', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('银行流水转日记账')).toBeVisible();
  await expect(page.getByText('流水上传')).toBeVisible();
});
```

- [ ] **Step 3: Run frontend e2e test**

Run:

```bash
cd frontend && npx playwright install chromium && npm run e2e
```

Expected: Playwright smoke test passes.

- [ ] **Step 4: Update README with full local runbook**

Add these sections to `README.md`:

```markdown
## Local Database

```bash
docker compose up -d postgres
```

## Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Verification

```bash
cd backend && pytest -q
cd frontend && npm run build && npm run e2e
```
```

- [ ] **Step 5: Commit**

Run:

```bash
git add frontend/playwright.config.ts frontend/tests README.md
git commit -m "test: add frontend smoke flow"
```

---

## Task 18: Replace In-Memory MVP Stores with SQLAlchemy Persistence

**Files:**

- Modify: `backend/app/services/template_service.py`
- Modify: `backend/app/services/conversion_service.py`
- Modify: `backend/app/services/confirmation_service.py`
- Modify: `backend/app/services/audit_service.py`
- Modify: `backend/app/api/deps.py`
- Modify: route files under `backend/app/api/routes/`
- Test: `backend/tests/integration/test_conversion_api.py`
- Test: `backend/tests/integration/test_export_api.py`

- [ ] **Step 1: Add database dependency**

Create `backend/app/api/deps.py`:

```python
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]
```

- [ ] **Step 2: Modify service functions to accept `Session`**

Update public service functions so route handlers pass `db: Session`.

Example signature:

```python
def create_bank_template(db: Session, payload: BankTemplateCreate) -> BankTemplateResponse:
    ...
```

- [ ] **Step 3: Persist immutable version records**

For create operations:

1. Insert parent record, such as `bank_templates`.
2. Insert version record with `version_no=1`.
3. Return parent plus latest version.

For new version operations:

1. Query current max version number.
2. Insert new version with `version_no=max_version + 1`.
3. Do not update old version rows.

- [ ] **Step 4: Persist conversion runs and preview rows**

When `POST /api/conversion-runs` succeeds:

1. Insert `conversion_runs`.
2. Insert one `conversion_run_files` row per source file.
3. Insert parsed `bank_transactions`.
4. Insert generated `journal_preview_rows`.
5. Insert `conversion_run_rule_versions`.
6. Store run summary in `summary_json`.

- [ ] **Step 5: Persist manual adjustments and confirmations**

When `PATCH /api/preview-rows/{id}` succeeds:

1. Insert `manual_adjustments`.
2. Update `journal_preview_rows.output_values_json`.
3. Update `journal_preview_rows.updated_at`.

When confirm succeeds:

1. Insert `confirmations`.
2. Update preview row status to `manually_confirmed`.

- [ ] **Step 6: Persist audit events**

Add audit event creation to:

```text
file.uploaded
bank_template.created
journal_template.created
mapping_profile.created
rule.created
conversion_run.created
preview_row.adjusted
preview_row.confirmed
export.created
```

- [ ] **Step 7: Run integration tests on PostgreSQL**

Run:

```bash
docker compose up -d postgres
cd backend && alembic upgrade head && pytest tests/integration -q
```

Expected: integration tests pass with PostgreSQL.

- [ ] **Step 8: Commit**

Run:

```bash
git add backend/app backend/tests/integration
git commit -m "feat: persist conversion workflow"
```

---

## Task 19: Final Verification and Acceptance Checklist

**Files:**

- Modify: `README.md`
- Create: `docs/mvp-acceptance-checklist.md`

- [ ] **Step 1: Create acceptance checklist**

Create `docs/mvp-acceptance-checklist.md` with:

```markdown
# MVP Acceptance Checklist

## Upload

- [ ] User can upload `bank_statement_basic.csv`.
- [ ] System returns file metadata with SHA-256 hash.
- [ ] Original file is stored under `.local/uploads`.

## Parse

- [ ] System parses two bank transactions.
- [ ] Income row is `credit` with positive net amount.
- [ ] Expense row is `debit` with negative net amount.

## Convert

- [ ] Rule-matched row receives journal summary and account subject.
- [ ] Unmatched row remains `needs_confirmation`.
- [ ] Missing required fields are flagged.

## Confirm

- [ ] User can manually set a missing field.
- [ ] User can confirm the row.
- [ ] Manual adjustment stores old value, new value, reason, user, and timestamp.

## Export

- [ ] User can export CSV.
- [ ] User can export XLSX.
- [ ] Exported columns match company journal template order.

## Traceability

- [ ] Export row links back to source file.
- [ ] Export row links back to source row number.
- [ ] Conversion run records template, mapping, and rule versions.
- [ ] Audit log records upload, conversion, adjustment, confirmation, and export.
```

- [ ] **Step 2: Run backend verification**

Run:

```bash
cd backend && ruff check . && pytest -q
```

Expected: ruff and pytest pass.

- [ ] **Step 3: Run frontend verification**

Run:

```bash
cd frontend && npm run build && npm run e2e
```

Expected: build and Playwright tests pass.

- [ ] **Step 4: Run manual local smoke flow**

Run backend:

```bash
cd backend && uvicorn app.main:app --reload
```

Run frontend:

```bash
cd frontend && npm run dev
```

Open:

```text
http://localhost:5173
```

Manual checks:

1. Upload `backend/tests/fixtures/bank_statement_basic.csv`.
2. Start conversion.
3. Confirm preview rows render.
4. Confirm one row is rule-filled.
5. Confirm unmatched row is marked for confirmation.
6. Export CSV.
7. Open CSV and verify columns.

- [ ] **Step 5: Commit final docs**

Run:

```bash
git add README.md docs/mvp-acceptance-checklist.md
git commit -m "docs: add mvp acceptance checklist"
```

---

## Self-Review Notes

Spec coverage:

1. Upload, file hash, and original file storage are covered by Tasks 4 and 10.
2. CSV/XLSX parsing, header detection, date parsing, and amount normalization are covered by Task 5.
3. Immutable template, mapping, and rule versions are covered by Tasks 3, 9, and 18.
4. Mapping and rules are covered by Tasks 6 and 7.
5. Preview row generation, exceptions, and confirmation status are covered by Task 8.
6. Manual adjustment and confirmation are covered by Task 11.
7. Export and processing file generation are covered by Task 12.
8. Audit logging is covered by Task 13 and persisted in Task 18.
9. Frontend workflow pages are covered by Tasks 14 through 16.
10. End-to-end smoke and acceptance are covered by Tasks 17 and 19.

Known sequencing decisions:

1. The first backend pass allows in-memory route stores so route shape and frontend work can start early.
2. SQLAlchemy persistence is completed in Task 18 after the core conversion behavior is already tested.
3. Celery/Redis is intentionally deferred until synchronous conversion is reliable.
4. Authentication is kept minimal for MVP; routes carry `user-1` in payloads until RBAC is hardened.

Execution recommendation:

Use subagent-driven development for Tasks 1 through 19. Review after each task and run the listed tests before moving to the next task.
