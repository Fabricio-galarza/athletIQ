from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from core.services.access_service import get_user_access_context


class AccessMeView(APIView):
    """
    Endpoint that returns current user's complete access context.
    Used by Train service and other modules.
    
    GET /api/v1/users/me/context/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        context = get_user_access_context(request.user)

        if context.get("plan") is None:
            return Response(
                {"error": "NO_ACTIVE_PLAN"},
                status=404
            )

        return Response(context)