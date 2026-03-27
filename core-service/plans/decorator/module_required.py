from rest_framework.response import Response
from rest_framework import status

from plans.services.access_service import user_has_module


def require_module(module_code):

    def decorator(view_func):

        def wrapper(self, request, *args, **kwargs):

            user = request.user

            # temporal mientras no hay auth
            if not user or user.is_anonymous:
                from users.models import User
                user = User.objects.first()

            if not user_has_module(user, module_code):
                return Response(
                    {
                        "error": "MODULE_NOT_ALLOWED",
                        "message": f"Module '{module_code}' is not available for this user"
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator