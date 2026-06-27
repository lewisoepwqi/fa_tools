from fastapi import APIRouter

from app.schemas.template import BankTemplateCreate, BankTemplateResponse
from app.services import template_service

router = APIRouter(prefix="/api/bank-templates", tags=["bank-templates"])


@router.post("", response_model=BankTemplateResponse)
def create_bank_template(payload: BankTemplateCreate) -> BankTemplateResponse:
    return template_service.create_bank_template(payload)


@router.get("", response_model=list[BankTemplateResponse])
def list_bank_templates(company_id: str | None = None) -> list[BankTemplateResponse]:
    return template_service.list_bank_templates(company_id)
