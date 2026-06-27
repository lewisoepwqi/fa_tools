from typing import Any

from pydantic import BaseModel


class ExportCreate(BaseModel):
    file_type: str
    columns: list[str]
    rows: list[dict[str, Any]]
    exported_by: str | None = None
    only_confirmed: bool = False
