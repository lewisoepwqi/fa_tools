# MVP Acceptance Checklist

## Upload
- [x] User can upload `bank_statement_basic.csv`.
- [x] System returns file metadata with SHA-256 hash.
- [x] Original file is stored under `.local/uploads`.
- [x] Source file metadata is persisted (`source_files`).

## Parse
- [x] System parses two bank transactions.
- [x] Income row is `credit` with positive net amount.
- [x] Expense row is `debit` with negative net amount.

## Convert
- [x] Rule-matched row receives journal summary and account subject.
- [x] Unmatched row remains `needs_confirmation`.
- [x] Missing required fields are flagged (`MISSING_REQUIRED_FIELD`).
- [x] Conversion run + transactions + preview rows persisted.

## Confirm
- [x] User can manually set a missing field (PATCH preview-row).
- [x] User can confirm the row (POST confirm).
- [x] Manual adjustment + confirmation persisted (`manual_adjustments`, `confirmations`).

## Export
- [x] User can export CSV.
- [x] User can export XLSX.
- [x] Exported columns match company journal template order.
- [x] Export persisted; download endpoint serves the file.
- [x] `only_confirmed` actually filters DB preview rows by status (was a no-op; P0-3 fixed).
- [x] Export validates required-field completeness, 422 on violation (P0-5).
- [x] Export generates a processing report (11 PRD §6.9.7 fields) with download endpoint (P0-4).

## Confirm (frontend closed-loop)
- [x] User can manually set a missing field (PATCH preview-row) — backend.
- [x] User can confirm the row (POST confirm) — backend.
- [x] Manual adjustment + confirmation persisted (`manual_adjustments`, `confirmations`).
- [x] Batch-detail page exposes edit / single-confirm / batch-confirm / status+exception filters (P0-6).

## Traceability
- [x] Export row links back to source file + source row number (`bank_transactions`).
- [x] Conversion run records rule versions (`conversion_run_rule_versions`).
- [x] Audit log records upload, template/rule/mapping creation, conversion, adjustment, confirmation, export (`audit_logs`).

## Template / mapping / rule versioning (editing = new version)
- [x] Editing any of the 4 versioned entities creates a new version via `POST /{id}/versions`; old versions are immutable (P0-1).
- [x] Version history available via `GET /{id}/versions` for all 4 entities (PRD §10.1.3).
- [x] Enable/disable via `PATCH /{id}/status` for all 4 entities (P2-4).
- [x] Rule priority reorder via `POST /api/rules/reorder` (P2-4).
- [x] Frontend: create + edit(new-version) + version-history + disable on all 4 entity list/detail pages.
- [x] Conversion run snapshots template/mapping version IDs for traceability (P0-2).

## Engine robustness
- [x] All 4 amount modes parse (`income_expense_columns` / `debit_credit_columns` / `single_amount_with_direction` / `signed_amount`) (P1-2).
- [x] Parse errors mark single-row exception codes (`INVALID_DATE`/`INVALID_AMOUNT`/`UNKNOWN_DIRECTION`/`MISSING_REQUIRED_FIELD`) instead of aborting the batch (P1-1).
- [x] Rule operators `gte`/`lte` are None-safe; date-range operators `date_gte`/`date_lte` added (P1-4 / P1-5).
- [x] `conditional` mapping type implemented (P1-6).
- [x] Header auto-detection wired: `POST /api/bank-templates/detect` recognizes header row / data start / field aliases / amount mode / date formats (P1-7 / P1-8).

## Audit
- [x] Audit log records `*.modified`, `*.disabled`/`*.enabled`, `rule.priority_changed` in addition to `*.created` (P2-3).

## Security (hardening applied during persistence migration)
- [x] Source-file resolution is DB-backed (no path traversal — unknown id → 404).
- [x] Export `file_type` constrained to `csv`/`xlsx` (422 on unknown).
- [x] Export download 404s when file missing on disk.

## Known follow-ups (out of MVP scope)
- [ ] PostgreSQL validation (tests use SQLite in-memory; `docker-compose.yml` + Alembic ready for PG).
- [ ] Bank-account / counterparty-account field encryption (stored plaintext for MVP).
- [ ] Dedup hashing (`bank_transactions.row_hash`) and balance-discontinuity detection (P1-3; handover §11).
- [ ] Authentication / RBAC (5 roles) — MVP has no auth (P2-1/P2-2; handover §11).
- [ ] Async task processing for large files (>10000 rows) — currently synchronous.
- [ ] Frontend bundle code-splitting (AntD single chunk) and static `message` context wiring.
- [ ] ip_address / user_agent capture in audit events.
- [ ] `DUPLICATE_IN_BATCH` / `DUPLICATE_HISTORY` / `BALANCE_DISCONTINUITY` detection (row_hash still empty).

> 2026-06-27 更新：`gap-analysis.md` 中所有标记为**【真缺口】**的 P0/P1/P2-3/P2-4 项
> （版本化编辑、批次快照、only_confirmed、必填校验、处理报告、前端确认闭环、
> 逐行异常、金额模式、conditional 映射、规则健壮性、表头自动识别、停用/重排、审计补全）
> 已全部实现并通过集成测试（后端 95 测试绿、ruff 绿；前端 build 绿、Playwright 3 绿）。
> 剩余项均为**【非 MVP / 已记录】**（认证 / PostgreSQL 实测 / 账号加密 / 去重历史 / 异步等）。
