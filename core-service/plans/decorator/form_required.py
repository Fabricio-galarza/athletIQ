from rest_framework.response import Response
from rest_framework import status

from core.services.access_service import user_has_form


# decorator to enforce form-level access control on endpoints
def require_form(form_name):

    # decorator wrapper that receives the view function
    def decorator(view_func):

        # actual wrapper executed on each request
        def wrapper(self, request, *args, **kwargs):

            user = request.user

            # user not authenticateds
            if not user or user.is_anonymous:
                return Response(
                    {"error": "AUTH_REQUIRED"},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # check if user has access to the required form
            if not user_has_form(user, form_name):
                return Response(
                    {
                        "error": "FORM_NOT_ALLOWED",
                        "message": f"Form '{form_name}' is not available for this user"
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # allow execution if access is granted
            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator