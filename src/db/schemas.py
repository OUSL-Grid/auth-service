
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    verified_domain: str

class UserRoleUpdate(BaseModel):
    id: str
    role: str