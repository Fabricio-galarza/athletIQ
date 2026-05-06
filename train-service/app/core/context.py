# app/core/context.py
"""
User context management for Train service.
Fetches context from Core or cache, validates JWT token.
"""

import base64
import json
import jwt
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import get_settings
from app.core.cache import cache

settings = get_settings()
logger = logging.getLogger(__name__)

security = HTTPBearer()


class FormField:
    """Represents a field in a dynamic form."""
    
    def __init__(self, data: Dict[str, Any]):
        self.id: Optional[UUID] = UUID(data["id"]) if data.get("id") else None
        self.name: str = data.get("name", "")
        self.label: str = data.get("label", "")
        self.type: str = data.get("type", "")
        self.required: bool = data.get("required", False)
        self.order: int = data.get("order", 0)
        
        # Get options based on field type
        self.options: List[Dict] = []
        ui_config = data.get("UI-config", {})
        
        if self.type == "multiselect":
            self.options = ui_config.get("options", [])
        else:
            self.options = data.get("options", [])
        
        self.ui_config = ui_config
    
    def validate(self, value: Any) -> tuple:
        """Validate a value against this field definition."""
        if self.required and (value is None or value == ""):
            return False, f"Field '{self.name}' is required"
        
        if value is None or value == "":
            return True, ""
        
        if self.type == "number":
            try:
                float(value)
            except (ValueError, TypeError):
                return False, f"Field '{self.name}' must be a number"
        
        # Validate JSON type
        elif self.type == "json":
            # JSON can be dict, list, string, number, bool, null
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                return False, f"Field '{self.name}' must be valid JSON"
        
        elif self.type in ["select", "radio"] and self.options:
            valid_values = [opt["value"] for opt in self.options]
            if str(value) not in valid_values:
                return False, f"Field '{self.name}' must be one of: {valid_values}"
        
        elif self.type == "multiselect" and self.options:
            valid_values = [opt["value"] for opt in self.options]
            if isinstance(value, list):
                for item in value:
                    if str(item) not in valid_values:
                        return False, f"Field '{self.name}' contains invalid value '{item}'"
            else:
                if str(value) not in valid_values:
                    return False, f"Field '{self.name}' must be one of: {valid_values}"
        
        return True, ""


class Form:
    """Represents a dynamic form with its fields."""
    
    def __init__(self, data: Dict[str, Any]):
        self.id: Optional[UUID] = UUID(data["id"]) if data.get("id") else None
        self.name: str = data.get("name", "")
        self.code: str = data.get("code", "")
        self.module: Optional[str] = data.get("module")
        self.fields: List[FormField] = [FormField(f) for f in data.get("fields", [])]
    
    def get_field(self, field_name: str) -> Optional[FormField]:
        """Get field by name."""
        for field in self.fields:
            if field.name == field_name:
                return field
        return None
    
    def validate_data(self, data: Dict[str, Any], partial: bool = False) -> Dict[str, Any]:
        """
        Validate dynamic form data against form schema.
        
        Args:
            data: Raw input data to validate
            partial: If True, don't require all required fields (for PATCH updates)
        
        Returns:
            Dict with field_name -> {"value": any, "field_id": UUID}
        
        Raises:
            ValidationError: If validation fails with details
        """
        from app.core.exceptions import ValidationError
        
        errors = {}
        validated = {}
        
        for field in self.fields:
            if partial and field.name not in data:
                continue
            
            value = data.get(field.name)
            is_valid, error_msg = field.validate(value)
            
            if not is_valid:
                errors[field.name] = [error_msg]
            else:
                validated[field.name] = {
                    "value": value,
                    "field_id": field.id
                }
        
        if errors:
            raise ValidationError("Form validation failed", details=errors)
        
        return validated
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert form to dictionary."""
        return {
            "id": str(self.id) if self.id else None,
            "name": self.name,
            "code": self.code,
            "module": self.module,
            "fields": [
                {
                    "id": str(f.id) if f.id else None,
                    "name": f.name,
                    "label": f.label,
                    "type": f.type,
                    "required": f.required,
                    "order": f.order,
                    "options": f.options,
                }
                for f in self.fields
            ]
        }


class UserContext:
    """Complete user context from Core service."""
    
    def __init__(self, data: Dict[str, Any]):
        self.user_id: str = data.get("user_id", "") or data.get("user", {}).get("id", "")
        self.email: str = data.get("email", "") or data.get("user", {}).get("email", "")
        self.roles: List[str] = data.get("roles", [])
        self.plans: List[str] = data.get("plans", [])
        self.features: List[str] = data.get("features", [])
        
        # Parse sports
        self.sports = []
        self.sports_map = {}
        for sport in data.get("sports", []):
            if isinstance(sport, dict):
                self.sports.append(sport.get("name", ""))
                self.sports_map[sport.get("name", "")] = sport.get("id", "")
            else:
                self.sports.append(sport)
        
        # Parse forms
        self.forms: List[Form] = [Form(f) for f in data.get("forms", [])]
    
    def is_athlete(self) -> bool:
        return "athlete" in self.roles
    
    def is_coach(self) -> bool:
        return "coach" in self.roles
    
    def has_sport(self, sport_name: str) -> bool:
        return sport_name in self.sports
    
    def get_sport_id(self, sport_name: str) -> Optional[str]:
        return self.sports_map.get(sport_name)
    
    def has_feature(self, feature: str) -> bool:
        return feature in self.features
    
    def get_form(self, form_code: str) -> Optional[Form]:
        for form in self.forms:
            if form.code == form_code:
                return form
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "roles": self.roles,
            "sports": self.sports,
            "forms": [f.to_dict() for f in self.forms],
        }


async def get_user_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_user_context: Optional[str] = Header(None, alias="X-User-Context"),
) -> UserContext:
    """Get user context from cache or request header."""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_signature": False}
        )
        user_id = payload.get("user_id", "")
    except Exception as e:
        logger.error(f"Token decode failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format"
        )
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing user_id in token"
        )
    
    cache_key = f"user_context:{user_id}"
    cached_context = await cache.get(cache_key)
    
    if cached_context:
        logger.debug(f"Context from CACHE for user {user_id}")
        return UserContext(cached_context)
    
    if not x_user_context:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Context header required. Please re-login."
        )
    
    try:
        context_json = base64.b64decode(x_user_context).decode('utf-8')
        context_data = json.loads(context_json)
        
        await cache.set(cache_key, context_data, ttl=1800)
        
        jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        return UserContext(context_data)
        
    except Exception as e:
        logger.error(f"Context error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


CurrentUser = Depends(get_user_context)


def require_role(role: str):
    """Factory for role-based access control."""
    async def _require(context: UserContext = Depends(get_user_context)):
        if role not in context.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' required"
            )
        return context
    return _require


RequireAthlete = require_role("athlete")
RequireCoach = require_role("coach")
RequireAdmin = require_role("admin")