


from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from src.auth.service import MagicLinkService
from src.core.dependencies import get_magic_link_service
from src.core.exceptions import DomainNotAllowedError, RateLimitExceededError

router = APIRouter(prefix="/auth", tags=["auth"])

class MagicLinkRequest(BaseModel):
    email: EmailStr



@router.post("/magic-link")
async def request_magic_link(
    payload: MagicLinkRequest,
    service: MagicLinkService = Depends(get_magic_link_service)
):
    try:
        await service.request_magic_link(payload.email)
    except DomainNotAllowedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except RateLimitExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))

    return {"message": "If this email is eligible, a magic link has been sent."}
    


