
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    verified_domain: str

class UserRoleUpdate(BaseModel):
    id: str
    role: str