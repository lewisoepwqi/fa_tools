from pydantic import BaseModel


class UploadedFileResponse(BaseModel):
    id: str
    company_id: str
    uploaded_by: str
    original_filename: str
    file_type: str
    file_size: int
    sha256: str
    storage_key: str
    status: str
