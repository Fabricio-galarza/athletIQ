import logging
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.core.cache import cache
import json

from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User
from permissions.models import Role
from plans.models import Feature, Plan
from sports.models import Sport
from forms.models import Form

logger = logging.getLogger(__name__)

@transaction.atomic
def login_user(data):
  
    """
    Handles CU-CORE-02:
    - validate credentials
    - request user from db
    - return all user data about session
    """
    
    try:
        email = data.get("email")
        password = data.get("password")
        
        # 🔹 validate credentials against db
        try:
            user = User.objects.get(email=email, is_active=True)
            if not user.check_password(password):
                raise ValueError("CREDENCIALES INVALIDAS")
        except ObjectDoesNotExist:
            raise ValueError("CREDENCIALES INVALIDAS")
        
        # 🔹 check if session is already cached to avoid unnecessary db queries
        cache_key = f"session:{user.id}"
        cached = cache.get(cache_key)
        if cached:
            return json.loads(cached)

        # 🔹 fetch roles assigned to the user
        roles = user.user_roles.values_list('role__name', flat=True)
        
        # 🔹 fetch active plans assigned to the user
        plans = Plan.objects.filter(user_plans__user=user).values_list("name", flat=True)
        
        # 🔹 fetch features enabled for the user's plans
        features = Feature.objects.filter(
            plan_features__plan__user_plans__user=user,
            plan_features__is_enabled=True
        ).values_list('code', flat=True)
        
        # 🔹 fetch sports practiced by the user
        sports_queryset = Sport.objects.filter(user_sports__user=user)
        
        # 🔹 fetch active forms available for the user's sports
        # prefetch_related avoids N+1 queries when accessing form_fields and their fields
        forms_qs = Form.objects.filter(
            is_active=True,
            sport_forms__sport__user_sports__user=user,
            plan_forms__plan__user_plans__user=user
        ).prefetch_related(
            'form_fields__field'
        ).distinct()
        
        # 🔹 serialize forms with their fields into a flat structure
        forms = [
                    {
                        "id": str(form.id),
                        "name": form.name,
                        "code": form.code,
                        "module": form.module.name,
                        "fields": [
                            {
                                "id": str(ff.field.id),  # 🔥 Agregar field_id
                                "name": ff.field.name,
                                "label": ff.label or ff.field.label,
                                "type": ff.field.field_type.code,
                                "required": ff.is_required,
                                "UI-config": ff.field.ui_config,
                                "order": ff.order,
                                "options": [
                                    {
                                        "value": opt.value,
                                        "label": opt.label or opt.value,
                                        "order": opt.order
                                    }
                                    for opt in ff.field.options.all().order_by('order')
                                ] if ff.field.field_type.code in ['select', 'radio', 'checkbox'] else []
                            }
                            for ff in form.form_fields.all().order_by('order')
                        ]
                    }
                    for form in forms_qs
                ]
        
        # 🔹 generate JWT tokens for the session
        # access token: short-lived, used in every request
        # refresh token: long-lived, used to renew the access token
        refresh = RefreshToken.for_user(user)
      
        # 🔹 build the session result
        result = {
            "token": str(refresh.access_token),  # quick access to access token
            "user": {
                "id": str(user.id),
                "email": user.email,
            },
            "roles": list(roles),
            "plans": list(plans),
            "features": list(features),
            "sports": [
                        {"id": str(sport.id), "name": sport.name}
                        for sport in sports_queryset
            ],
            "forms": forms,
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            }
        }
    
        # 🔹 cache the session for 30 minutes to speed up subsequent logins
        cache.set(cache_key, json.dumps(result), timeout=60*30)
      
        return result
     
    except Exception as e:
        logger.error("Error durante el inicio de sesión", exc_info=True)
        raise e