from pydantic import BaseModel


class ManualAdjustmentRequest(BaseModel):
    field_name: str
    new_value: str
    reason: str | None = None
    adjusted_by: str


class ConfirmationRequest(BaseModel):
    confirmed_by: str
    comment: str | None = None
