from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from plans.services.access_service import get_user_features
from users.models import User


class UserFeaturesView(APIView):

    def get(self, request):

        user = request.user

        # 🔥 temporal si no tienes auth aún
        if not user or user.is_anonymous:
            return Response(
                {
                    "error": "UNAUTHORIZED",
                    "message": "User not authenticated"
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        result = get_user_features(user)

        if not result:
            return Response(
                {
                    "error": "NO_ACTIVE_PLAN",
                    "message": "User does not have an active plan"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(result, status=status.HTTP_200_OK)