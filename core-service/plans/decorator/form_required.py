from rest_framework.response import Response
from rest_framework import status

from plans.services.access_service import user_has_form


# decorator to enforce form-level access control on endpoints
def require_form(form_name):

    # decorator wrapper that receives the view function
    def decorator(view_func):

        # actual wrapper executed on each request
        def wrapper(self, request, *args, **kwargs):

            user = request.user

            # temporary fallback while authentication is not implemented
            # this should be removed once JWT auth is in place
            if not user or user.is_anonymous:
                from users.models import User
                user = User.objects.first()

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