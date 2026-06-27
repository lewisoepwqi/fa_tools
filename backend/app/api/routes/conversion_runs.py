from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.enums import AmountMode
from app.schemas.conversion import (
    ConversionRunCreate,
    ConversionRunResponse,
    ConversionRunSummary,
    JournalPreviewRowData,
)
from app.services.conversion_service import build_preview_row
from app.services.parser_service import BankTemplateParseConfig, parse_bank_statement

router = APIRouter(prefix="/api/conversion-runs", tags=["conversion-runs"])


@router.post("", response_model=ConversionRunResponse)
def start_conversion_run(payload: ConversionRunCreate) -> ConversionRunResponse:
    upload_dir = Path(get_settings().upload_dir)
    config = payload.bank_parse_config
    amount_mode = AmountMode(config.amount_mode)

    preview_rows: list[JournalPreviewRowData] = []
    row_index = 1
    for source_file_id in payload.source_file_ids:
        file_path = upload_dir / f"{source_file_id}.{config.file_type}"
        parse_config = BankTemplateParseConfig(
            bank_account_id=payload.bank_account_id,
            source_file_id=source_file_id,
            file_type=config.file_type,
            sheet_name=config.sheet_name,
            header_row_index=config.header_row_index,
            data_start_row_index=config.data_start_row_index,
            field_aliases=config.field_aliases,
            amount_mode=amount_mode,
            amount_config=config.amount_config,
            date_formats=config.date_formats,
        )
        transactions = parse_bank_statement(file_path, parse_config)
        for transaction in transactions:
            preview_rows.append(
                build_preview_row(
                    transaction,
                    payload.mappings,
                    payload.rules,
                    payload.required_columns,
                    row_index,
                )
            )
            row_index += 1

    return ConversionRunResponse(
        id=str(uuid4()),
        status="completed",
        summary=ConversionRunSummary(total_rows=len(preview_rows)),
        preview_rows=preview_rows,
    )
