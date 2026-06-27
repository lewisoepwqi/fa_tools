from app.models.file import SourceFile
from app.models.user import User
from app.tools.bank_journal.models.conversion import JournalPreviewRow
from app.tools.bank_journal.models.rule import RuleVersion
from app.tools.bank_journal.models.template import (
    BankTemplateVersion,
    CompanyJournalTemplateVersion,
)


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


def test_versioned_models_expose_reviewed_contract_columns() -> None:
    company_version_columns = set(CompanyJournalTemplateVersion.__table__.columns.keys())
    source_file_columns = set(SourceFile.__table__.columns.keys())
    rule_version_columns = set(RuleVersion.__table__.columns.keys())
    preview_columns = set(JournalPreviewRow.__table__.columns.keys())

    assert {
        "file_type",
        "sheet_name",
        "header_row_index",
        "data_start_row_index",
        "columns_json",
        "required_columns_json",
        "format_rules_json",
    } <= company_version_columns
    assert "original_filename" in source_file_columns
    assert {"conditions_json", "actions_json", "allow_auto_confirm"} <= rule_version_columns
    assert {"output_values_json", "exception_codes_json"} <= preview_columns


def test_defaulted_model_columns_have_server_defaults() -> None:
    assert User.__table__.c.status.server_default is not None
    assert SourceFile.__table__.c.status.server_default is not None
    assert RuleVersion.__table__.c.allow_auto_confirm.server_default is not None
    assert JournalPreviewRow.__table__.c.status.server_default is not None
