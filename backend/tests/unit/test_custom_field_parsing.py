"""扩展字段的解析链路测试。

覆盖：给定 CustomFieldDef，detect 识别 + parse 填充 extra_fields（text/amount/date）。
这是端到端验证扩展字段进入 model_dump（规则/映射引擎据此可用）的关键。
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from app.tools.bank_journal.enums import AmountMode
from app.tools.bank_journal.services.parser_service import (
    BankTemplateParseConfig,
    CustomFieldDef,
    detect_bank_template_config,
    parse_bank_rows,
)


def _config_with_custom(file_type: str, customs: list[CustomFieldDef]) -> BankTemplateParseConfig:
    return BankTemplateParseConfig(
        bank_account_id="bank-1",
        source_file_id="file-1",
        file_type=file_type,
        sheet_name="Sheet1",
        header_row_index=0,
        data_start_row_index=1,
        field_aliases={
            "交易日期": "transaction_date",
            "收入": "income_amount",
            "支出": "expense_amount",
            "余额": "balance",
        },
        amount_mode=AmountMode.INCOME_EXPENSE_COLUMNS,
        amount_config={"income": "income_amount", "expense": "expense_amount"},
        date_formats=["%Y-%m-%d"],
        custom_fields=customs,
    )


def test_detect_recognizes_custom_header_keyword(tmp_path: Path) -> None:
    """detect 时扩展字段的中文关键词被识别进 field_aliases。"""
    fixture = tmp_path / "stmt.csv"
    fixture.write_text(
        "交易日期,收入,支出,余额,成本中心\n2026-06-01,100,0,100,A部\n",
        encoding="utf-8",
    )
    customs = [
        CustomFieldDef(
            field_key="cost_center",
            slot_key="ext_text_1",
            data_type="text",
            header_keywords=["成本中心"],
        )
    ]
    detected = detect_bank_template_config(fixture, "csv", "Sheet1", customs)
    aliases = detected["field_aliases"]
    assert aliases.get("成本中心") == "cost_center"


def test_parse_fills_text_custom_field(tmp_path: Path) -> None:
    fixture = tmp_path / "stmt.csv"
    fixture.write_text(
        "交易日期,收入,支出,余额,成本中心\n2026-06-01,100.00,0.00,100.00,A部门\n",
        encoding="utf-8",
    )
    customs = [
        CustomFieldDef(
            field_key="cost_center",
            slot_key="ext_text_1",
            data_type="text",
            header_keywords=["成本中心"],
        )
    ]
    config = _config_with_custom("csv", customs)
    # 关键：field_aliases 必须含成本中心→cost_center，解析才取得到值
    config.field_aliases["成本中心"] = "cost_center"
    rows = parse_bank_rows(fixture, config)
    assert len(rows) == 1
    txn = rows[0].transaction
    assert txn is not None
    assert txn.extra_fields["cost_center"] == "A部门"


def test_parse_fills_amount_and_date_custom_fields(tmp_path: Path) -> None:
    fixture = tmp_path / "stmt.csv"
    fixture.write_text(
        "交易日期,收入,支出,余额,项目金额,立项日\n"
        "2026-06-01,100.00,0.00,100.00,1234.56,2026-05-01\n",
        encoding="utf-8",
    )
    customs = [
        CustomFieldDef(
            field_key="project_amount",
            slot_key="ext_amount_1",
            data_type="amount",
            header_keywords=["项目金额"],
        ),
        CustomFieldDef(
            field_key="setup_date",
            slot_key="ext_date_1",
            data_type="date",
            header_keywords=["立项日"],
        ),
    ]
    config = _config_with_custom("csv", customs)
    config.field_aliases["项目金额"] = "project_amount"
    config.field_aliases["立项日"] = "setup_date"
    rows = parse_bank_rows(fixture, config)
    txn = rows[0].transaction
    assert txn.extra_fields["project_amount"] == Decimal("1234.56")
    assert txn.extra_fields["setup_date"] == "2026-05-01"


def test_parse_extra_fields_absent_without_customs(tmp_path: Path) -> None:
    """无扩展字段时 extra_fields 为空（回归：不影响核心解析）。"""
    fixture = tmp_path / "stmt.csv"
    fixture.write_text(
        "交易日期,收入,支出,余额\n2026-06-01,100.00,0.00,100.00\n",
        encoding="utf-8",
    )
    config = _config_with_custom("csv", customs=[])
    rows = parse_bank_rows(fixture, config)
    txn = rows[0].transaction
    assert txn.extra_fields == {}


def test_parse_skips_invalid_custom_date_does_not_abort_row(tmp_path: Path) -> None:
    """扩展日期字段解析失败不阻断整行（核心字段已成功），仅跳过该字段。"""
    fixture = tmp_path / "stmt.csv"
    fixture.write_text(
        "交易日期,收入,支出,余额,立项日\n2026-06-01,100.00,0.00,100.00,not-a-date\n",
        encoding="utf-8",
    )
    customs = [
        CustomFieldDef(
            field_key="setup_date",
            slot_key="ext_date_1",
            data_type="date",
            header_keywords=["立项日"],
        )
    ]
    config = _config_with_custom("csv", customs)
    config.field_aliases["立项日"] = "setup_date"
    rows = parse_bank_rows(fixture, config)
    txn = rows[0].transaction
    assert txn is not None  # 核心行仍解析成功
    assert "setup_date" not in txn.extra_fields  # 非法日期被跳过


# 抑制未使用 import 警告（date 在未来 date 断言中使用）
_ = date
