from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class InviteRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=160)
    role: str
    tenant_name: str | None = Field(default=None, max_length=160)


class InviteResponse(BaseModel):
    invitation_id: str
    invite_token: str
    expires_in: int
    tenant_id: str | None = None


class CreateTenantRequest(BaseModel):
    tenant_name: str = Field(min_length=1, max_length=160)
    owner_email: EmailStr
    owner_name: str = Field(min_length=1, max_length=160)


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=12, max_length=256)


class UserSummary(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool


class ChangeRoleRequest(BaseModel):
    role: str


class TenantSummary(BaseModel):
    id: str
    name: str
