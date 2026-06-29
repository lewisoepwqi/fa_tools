from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CompanyRef(BaseModel):
    id: str
    name: str


class MeResponse(BaseModel):
    id: str
    email: str
    name: str | None = None
    roles: list[str]
    accessible_companies: list[CompanyRef] | str  # "all" 或公司列表
