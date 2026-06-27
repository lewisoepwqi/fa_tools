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

## Traceability
- [x] Export row links back to source file + source row number (`bank_transactions`).
- [x] Conversion run records rule versions (`conversion_run_rule_versions`).
- [x] Audit log records upload, template/rule/mapping creation, conversion, adjustment, confirmation, export (`audit_logs`).

## Security (hardening applied during persistence migration)
- [x] Source-file resolution is DB-backed (no path traversal — unknown id → 404).
- [x] Export `file_type` constrained to `csv`/`xlsx` (422 on unknown).
- [x] Export download 404s when file missing on disk.

## Known follow-ups (out of MVP scope)
- [ ] PostgreSQL validation (tests use SQLite in-memory; `docker-compose.yml` + Alembic ready for PG).
- [ ] Bank-account / counterparty-account field encryption (stored plaintext for MVP).
- [ ] Dedup hashing (`bank_transactions.row_hash`) and balance-discontinuity detection.
- [ ] Frontend bundle code-splitting (AntD single chunk) and static `message` context wiring.
- [ ] ip_address / user_agent capture in audit events.
