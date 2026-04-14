import logging
from django.db import transaction
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ObjectDoesNotExist

from users.models import User
from users.models import Profile
from permissions.models import Role, UserRole
from plans.models import Plan, UserPlan

logger = logging.getLogger(__name__)


# orchestrates full user registration flow
@transaction.atomic
def register_user(data):
    """
    Handles CU-CORE-01:
    - creates user
    - creates profile
    - assigns default role
    - assigns default plan
    """
    try:
        email = data.get("email")
        password = data.get("password")
        profile_data = data.pop('profile')
        first_name = profile_data.get("first_name")
        last_name = profile_data.get("last_name")
        

        # 🔹 validate email uniqueness
        if User.objects.filter(email=email).exists():
            
            raise ValueError("CORREO ELECTRONICO YA EXISTE")

        # 🔹 create user
        user = User.objects.create(
            email=email,
            password=make_password(password),
            is_active=True
        )

        # 🔹 create profile
        Profile.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name
        )

        # 🔹 get default role
        try:
            role = Role.objects.get(code="athlete")
        except ObjectDoesNotExist:
            logger.error("Rol no configurado", exc_info=True)
            raise Exception("ROL NO CONFIGURADO")

        # 🔹 assign role
        UserRole.objects.create(
            user=user,
            role=role
        )

        # 🔹 get default plan
        try:
            plan = Plan.objects.get(name="basic")
        except ObjectDoesNotExist:
            logger.error("Plan no configurado", exc_info=True)
            raise Exception("PLAN NO CONFIGURADO")
        

        # 🔹 assign plan
        UserPlan.objects.create(
            user=user,
            plan=plan,
            is_active=True
        )

        return {
            "id": str(user.id),
            "email": user.email,
            "first_name": first_name,
            "last_name": last_name,
            "role": role.name,
            "plan": plan.name,
        }
    except Exception as e:
        logger.error("Error durante el registro del usuario", exc_info=True)
        raise e