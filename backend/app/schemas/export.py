from typing import Any, Literal

from pydantic import BaseModel


class ExportCreate(BaseModel):
    file_type: Literal["csv", "xlsx"]
    columns: list[str]
    rows: list[dict[str, Any]]
    exported_by: str | None = None
    only_confirmed: bool = False
