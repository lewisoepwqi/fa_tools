from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.sql.sqltypes import Numeric

from app.core.config import get_settings


def _normalized_default(column_default: object) -> str:
    return str(column_default).strip().strip("()").strip("'").strip('"').lower()


def test_initial_migration_matches_contract(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "migration_contract.sqlite3"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    alembic_cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))

    try:
        command.upgrade(alembic_cfg, "head")

        engine = create_engine(database_url)
        inspector = inspect(engine)

        source_file_columns = {column["name"] for column in inspector.get_columns("source_files")}
        assert {"original_filename", "sha256", "storage_key"} <= source_file_columns
        source_file_status = next(
            column for column in inspector.get_columns("source_files") if column["name"] == "status"
        )
        assert _normalized_default(source_file_status["default"]) == "pending"

        rule_version_columns = {column["name"] for column in inspector.get_columns("rule_versions")}
        assert {"conditions_json", "actions_json", "allow_auto_confirm"} <= rule_version_columns
        allow_auto_confirm = next(
            column
            for column in inspector.get_columns("rule_versions")
            if column["name"] == "allow_auto_confirm"
        )
        assert _normalized_default(allow_auto_confirm["default"]) in {"0", "false"}

        export_only_confirmed = next(
            column for column in inspector.get_columns("exports") if column["name"] == "only_confirmed"
        )
        assert _normalized_default(export_only_confirmed["default"]) in {"0", "false"}

        bank_account_currency = next(
            column for column in inspector.get_columns("bank_accounts") if column["name"] == "currency"
        )
        assert _normalized_default(bank_account_currency["default"]) == "cny"

        bank_transaction_columns = {
            column["name"]: column for column in inspector.get_columns("bank_transactions")
        }
        net_amount_type = bank_transaction_columns["net_amount"]["type"]
        assert isinstance(net_amount_type, Numeric)
        if net_amount_type.precision is not None:
            assert net_amount_type.precision == 18
        if net_amount_type.scale is not None:
            assert net_amount_type.scale == 2

        preview_columns = {column["name"] for column in inspector.get_columns("journal_preview_rows")}
        assert {
            "output_values_json",
            "exception_codes_json",
            "matched_rule_versions_json",
            "rule_trace_json",
        } <= preview_columns
        preview_status = next(
            column
            for column in inspector.get_columns("journal_preview_rows")
            if column["name"] == "status"
        )
        assert _normalized_default(preview_status["default"]) == "needs_confirmation"

        command.downgrade(alembic_cfg, "base")

        remaining_tables = set(inspect(engine).get_table_names())
        assert "users" not in remaining_tables
        assert "source_files" not in remaining_tables
        assert "journal_preview_rows" not in remaining_tables
    finally:
        get_settings.cache_clear()
