
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    verified_domain: str

class UserRoleUpdate(BaseModel):
    id: str
    role: str


from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionCreate(BaseModel):
    user_id: str
    refresh_token_hash: str
    expires_at: datetime
    user_agent: str | None = None
    ip_address: str | None = None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    user_agent: str | None
    ip_address: str | None

class OAuthIdentityCreate(BaseModel):
    user_id: str
    provider: str
    provider_user_id: str
    access_token_enc: str | None = None

class OTPCodeCreate(BaseModel):
    user_id: str
    code_hash: str
    purpose: str
    expires_at: datetime