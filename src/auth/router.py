


from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from src.auth.service import MagicLinkService
from src.core.dependencies import get, get_magic_link_service

router = APIRouter(prefix="/auth", tags=["auth"])

class MagicLinkRequest(BaseModel):
    email: EmailStr



@router.post("/magic-link")
async def request_magic_link(
    payload: MagicLinkRequest,
    service: MagicLinkService = Depends(get_magic_link_service)
):
    


