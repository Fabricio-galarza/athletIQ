from rest_framework.response import Response
from rest_framework import status

from core.services.access_service import user_has_module

# decorator to enforce form-level access control on endpoints
def require_module(module_code):

     # decorator wrapper that receives the view function
    def decorator(view_func):

        def wrapper(self, request, *args, **kwargs):

            user = request.user

            # not authenticated
            if not user or user.is_anonymous:
                return Response(
                    {"error": "AUTH_REQUIRED"},
                    status=status.HTTP_401_UNAUTHORIZED
                )

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