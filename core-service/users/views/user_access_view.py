from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.services.access_service import get_user_access_context


class UserAccessView(APIView):

    def get(self, request):

        user = request.user

        # temporal mientras no tienes auth
        if not user or user.is_anonymous:
            from users.models import User
            user = User.objects.first()

        result = get_user_access_context(user)

        if not result:
            return Response(
                {
                    "error": "NO_ACTIVE_PLAN",
                    "message": "User does not have an active plan"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(result, status=status.HTTP_200_OK)