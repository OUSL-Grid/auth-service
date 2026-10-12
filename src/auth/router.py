


import secrets
from typing import Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr

from src.auth.claims import Claims
from src.auth.google_service import GoogleAuthService
from src.auth.oauth_google import GoogleOAuthClient, OAuthStateCodec
from src.auth.rbac import ADMIN, require_role
from src.auth.service import MagicLinkService
from src.core.dependencies import get_cookie_secure, get_current_claims, get_db, get_frontend_url, get_google_auth_service, get_google_client, get_magic_link_service, get_state_codec
from src.core.exceptions import AccountDisabledError, CodeConsumedError, CodeExpiredError, CodeLockedError, CodeNotFoundError, DomainNotAllowedError, OAuthEmailNotVerifiedError, OAuthExchangeError, OAuthIdTokenError, OAuthStateError, RateLimitExceededError, UserNotFoundError
from src.auth.jwt import TokenPair
from src.db.schemas import UserRoleUpdate
from src.db.user_repository import UserRepository
from sqlalchemy.ext.asyncio import AsyncSession




router = APIRouter(tags=["auth"])

class MagicLinkRequest(BaseModel):
    email: EmailStr

class RoleChange(BaseModel):
    role: Literal["student", "moderator", "admin"]

def get_user_repo(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)

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

@router.get("/me", response_model=Claims)
async def me(claims: Claims = Depends(get_current_claims)):
    return claims

@router.patch("/users/{user_id}/role")
async def change_role(
    user_id: str,
    body: RoleChange,
    claims: Claims = Depends(require_role(ADMIN)),
    user_repo: UserRepository = Depends(get_user_repo),
):
    try:
        user = await user_repo.update_role(UserRoleUpdate(id=user_id, role=body.role))
    except UserNotFoundError:
        raise HTTPException(404, "User not found")
    return {"id": user.id, "role": user.role}

STATE_COOKIE = "oauth_state"
_RESTART = "Sign-in session not found or expired. Please start again."


@router.get("/google/login", name="google_login")
async def google_login(
    request: Request,
    google: GoogleOAuthClient = Depends(get_google_client),
    codec: OAuthStateCodec = Depends(get_state_codec),
    cookie_secure: bool = Depends(get_cookie_secure),
):
    auth_request = google.build_authorization_request()
    response = RedirectResponse(auth_request.url, status_code=302)
    response.set_cookie(
        STATE_COOKIE,
        codec.dumps(auth_request),
        max_age=600,
        httponly=True,
        secure=cookie_secure,
        samesite="lax",  # strict would drop the cookie on the redirect back from Google
        path=request.url_for("google_callback").path,
    )
    return response

@router.get("/google/callback", name="google_callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    service: GoogleAuthService = Depends(get_google_auth_service),
    codec: OAuthStateCodec = Depends(get_state_codec),
    frontend_url: str = Depends(get_frontend_url),
):
    def redirect(url: str) -> RedirectResponse:
        resp = RedirectResponse(url, status_code=302)
        resp.delete_cookie(STATE_COOKIE, path=request.url.path)  # one-shot
        return resp

    def fail(reason: str) -> RedirectResponse:
        return redirect(f"{frontend_url}/login?{urlencode({'error': reason})}")

    if error or not code or not state:
        return fail("cancelled")

    cookie = request.cookies.get(STATE_COOKIE)
    if not cookie:
        return fail("session_expired")
    try:
        saved = codec.loads(cookie)
    except OAuthStateError:
        return fail("session_expired")
    if not secrets.compare_digest(saved["state"].encode(), state.encode()):
        return fail("session_expired")

    try:
        login_code = await service.handle_callback(code, saved["verifier"], saved["nonce"])
    except (OAuthExchangeError, OAuthIdTokenError):
        return fail("google_failed")
    except DomainNotAllowedError:
        return fail("domain_not_allowed")
    except OAuthEmailNotVerifiedError:
        return fail("email_not_verified")
    except AccountDisabledError:
        return fail("account_disabled")

    # fragment (#), not query (?): never sent to servers, logged, or put in Referer
    return redirect(f"{frontend_url}/auth/callback#code={login_code}")


class ExchangeRequest(BaseModel):
    code: str


@router.post("/token/exchange", response_model=TokenPair)
async def exchange_login_code(
    body: ExchangeRequest,
    request: Request,
    response: Response,
    service: GoogleAuthService = Depends(get_google_auth_service),
):
    try:
        pair = await service.exchange_login_code(
            body.code,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except (CodeNotFoundError, CodeLockedError):
        raise HTTPException(400, "This sign-in code is invalid.")
    except (CodeExpiredError, CodeConsumedError):
        raise HTTPException(410, "This sign-in code has expired. Please sign in again.")
    except AccountDisabledError as e:
        raise HTTPException(403, str(e))

    response.headers["Cache-Control"] = "no-store"
    return pair