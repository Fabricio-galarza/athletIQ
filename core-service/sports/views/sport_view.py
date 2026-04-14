from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from sports.services.sport_service import get_available_sports
from sports.serializers.sport_serializer import SportSerializer

class sportListview(APIView):

    # only authenticated users
    permission_classes = [IsAuthenticated]

    def get(self, request):

        # get available sports
        sports = get_available_sports(user=request.user)

        #seralize response
        serializer = SportSerializer(sports, many=True)

        return Response(serializer.data)

