import asyncio
import base64
import hashlib
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt
from itsdangerous import BadData, URLSafeTimedSerializer

from src.core.exceptions import OAuthExchangeError, OAuthIdTokenError, OAuthStateError

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ["https://accounts.google.com", "accounts.google.com"]

KeyResolver = Callable[[str], Awaitable[object]]


@dataclass(frozen=True)
class AuthorizationRequest:
    url: str
    state: str
    nonce: str
    code_verifier: str


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    hosted_domain: str | None


class GoogleKeyResolver:
    """Looks up Google's signing key for an ID token (PyJWKClient caches the key set)."""

    def __init__(self, jwks_url: str = GOOGLE_JWKS_URL):
        self._client = jwt.PyJWKClient(jwks_url)

    async def __call__(self, id_token: str):
        # PyJWKClient does blocking network I/O, so keep it off the event loop
        signing_key = await asyncio.to_thread(self._client.get_signing_key_from_jwt, id_token)
        return signing_key.key


class GoogleOAuthClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        hosted_domain_hint: str | None = None,
        key_resolver: KeyResolver | None = None,
        transport: httpx.AsyncBaseTransport | None = None,  # lets tests mock Google
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.hosted_domain_hint = hosted_domain_hint
        self._key_resolver = key_resolver or GoogleKeyResolver()
        self._transport = transport

    def build_authorization_request(self) -> AuthorizationRequest:
        state = secrets.token_urlsafe(32)   # ties the callback to this browser (CSRF)
        nonce = secrets.token_urlsafe(32)   # ties the ID token to this login attempt
        verifier = secrets.token_urlsafe(64)  # PKCE
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        if self.hosted_domain_hint:
            params["hd"] = self.hosted_domain_hint
        return AuthorizationRequest(
            url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}",
            state=state,
            nonce=nonce,
            code_verifier=verifier,
        )

    async def exchange_code(self, code: str, code_verifier: str) -> dict:
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        }
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=10) as client:
                resp = await client.post(GOOGLE_TOKEN_URL, data=data)
            if resp.status_code != 200:
                raise OAuthExchangeError("Google rejected the authorization code")
            body = resp.json()
        except httpx.HTTPError as e:
            raise OAuthExchangeError("Could not reach Google") from e
        except ValueError as e:
            raise OAuthExchangeError("Unreadable response from Google") from e

        if "id_token" not in body:
            raise OAuthExchangeError("Google response did not include an ID token")
        return body

    async def verify_id_token(self, id_token: str, expected_nonce: str) -> GoogleIdentity:
        try:
            key = await self._key_resolver(id_token)
            claims = jwt.decode(
                id_token,
                key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=GOOGLE_ISSUERS,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as e:
            raise OAuthIdTokenError("Invalid Google ID token") from e

        nonce = str(claims.get("nonce", ""))
        if not secrets.compare_digest(nonce.encode(), expected_nonce.encode()):
            raise OAuthIdTokenError("ID token nonce mismatch")

        email = claims.get("email")
        if not email:
            raise OAuthIdTokenError("ID token has no email")

        return GoogleIdentity(
            sub=claims["sub"],
            email=email.lower(),
            email_verified=str(claims.get("email_verified")).lower() == "true",
            hosted_domain=claims.get("hd"),
        )


class OAuthStateCodec:
    """Signs the per-login secrets (state, nonce, PKCE verifier) into a short-lived cookie value."""

    def __init__(self, secret: str, max_age_seconds: int = 600):
        self._serializer = URLSafeTimedSerializer(secret, salt="google-oauth-state")
        self._max_age = max_age_seconds

    def dumps(self, req: AuthorizationRequest) -> str:
        return self._serializer.dumps(
            {"state": req.state, "nonce": req.nonce, "verifier": req.code_verifier}
        )

    def loads(self, value: str) -> dict:
        try:
            return self._serializer.loads(value, max_age=self._max_age)
        except BadData as e:  # bad signature, expired, or malformed
            raise OAuthStateError("Invalid or expired sign-in session") from e