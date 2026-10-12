


from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr

from src.auth.service import MagicLinkService
from src.core.dependencies import get_magic_link_service
from src.core.exceptions import AccountDisabledError, CodeConsumedError, CodeExpiredError, CodeNotFoundError, DomainNotAllowedError, RateLimitExceededError
from src.auth.jwt import TokenPair

router = APIRouter(tags=["auth"])

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
    

@router.get("/verify", response_model=TokenPair)
async def verify_magic_link(
    token: str,
    request: Request,
    service: MagicLinkService = Depends(get_magic_link_service),
):
    try:
        return await service.verify_magic_link(
            token,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except CodeNotFoundError:
        raise HTTPException(400, "This sign-in link is invalid.")
    except CodeExpiredError:
        raise HTTPException(410, "This sign-in link has expired. Please request a new one.")
    except CodeConsumedError:
        raise HTTPException(410, "This sign-in link has already been used. Please request a new one.")
    except DomainNotAllowedError as e:
        raise HTTPException(403, str(e))
    except AccountDisabledError as e:
        raise HTTPException(403, str(e)) 
