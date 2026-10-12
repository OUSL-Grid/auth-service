




from fastapi import Depends, HTTPException

from src.auth.claims import Claims
from src.core.dependencies import get_current_claims


STUDENT = "student"
MODERATOR = "moderator"
ADMIN = "admin"
VALID_ROLES = frozenset({STUDENT, MODERATOR, ADMIN})



def require_role(*allowed_roles: str):

    if not allowed_roles:
        raise ValueError("require_role needs at least one role")
    unknown = set(allowed_roles) - VALID_ROLES

    if unknown:
        raise ValueError(f"Unknown role(s): {sorted(unknown)}")

    async def checker(claims: Claims = Depends(get_current_claims)):
        if claims.role not in allowed_roles:
            raise HTTPException(403, "You do not have permission to perform this action")
        return claims
    return checker
    