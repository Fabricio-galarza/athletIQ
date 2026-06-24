"""
Authentication - Decode JWT token from Core (Django Simple JWT)
"""

import jwt
import logging
from typing import Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

security = HTTPBearer()


class UserContext:
    def __init__(self, payload: Dict[str, Any]):
        # Django Simple JWT usa 'user_id' en lugar de 'sub'
        self.user_id: str = str(payload.get("user_id", ""))
        self.email: str = payload.get("email", "")
        self.roles: list = payload.get("roles", [])
        self.permissions: list = payload.get("permissions", [])
        self.plan: Dict = payload.get("plan", {})
        self.features: list = payload.get("features", [])
        self.modules: list = payload.get("modules", [])
        self.sports: list = payload.get("sports", [])
    
    def has_sport(self, sport_id: str) -> bool:
        return sport_id in self.sports
    
    def is_athlete(self) -> bool:
        return "athlete" in self.roles
    
    def is_coach(self) -> bool:
        return "coach" in self.roles


async def get_user_context(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserContext:
    token = credentials.credentials

    try:
        # Decode JWT token from Django Simple JWT
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        logger.info(f"User authenticated: {payload.get('user_id')}")

        return UserContext(payload)
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token ({type(e).__name__}): {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except Exception as e:
        logger.error(f"Unexpected authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


async def require_athlete(context: UserContext = Depends(get_user_context)) -> UserContext:
    if not context.is_athlete():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Athlete role required"
        )
    return context


async def require_coach(context: UserContext = Depends(get_user_context)) -> UserContext:
    if not context.is_coach():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Coach role required"
        )
    return context