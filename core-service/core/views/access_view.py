from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.services.access_service import get_user_access_context


# endpoint that returns current user's access context
class AccessMeView(APIView):

    # require authenticated user
    permission_classes = [IsAuthenticated]

    def get(self, request):

        # get access context
        context = get_user_access_context(request.user)

        # if user has no active plan
        if not context:
            return Response(
                {"error": "NO_ACTIVE_PLAN"},
                status=404
            )

        return Response(context)