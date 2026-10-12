
import jwt



from pydantic import BaseModel, ValidationError

from src.core.exceptions import TokenExpiredError, TokenInvalidError


class Claims(BaseModel):
    user_id: str
    verified_domain: str
    role: str
    trust_score: float
    iss: str
    iat: int
    exp: int

def decode_access_token(token: str, public_key: str, issuer: str) -> Claims:
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"], 
            issuer=issuer,
            options={"require": ["exp", "iat", "iss", "user_id"]},
        )

    except jwt.ExpiredSignatureError as e:  # must come first: it subclasses InvalidTokenError
        raise TokenExpiredError("Access token has expired") from e
    except jwt.InvalidTokenError as e:
        raise TokenInvalidError("Access token is invalid") from e

    try:
        return Claims(**payload)
    except ValidationError as e:
        raise TokenInvalidError("Access token claims are malformed") from e