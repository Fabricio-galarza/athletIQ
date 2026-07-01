from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from sports.serializers.user_sport_serializer import UserSportSerializer
from sports.services.user_sport_service import update_user_sports, get_user_sports
from sports.serializers.sport_serializer import SportSerializer


class UserSportView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        sports = get_user_sports(user=request.user)
        serializer = SportSerializer(sports, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = UserSportSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        update_user_sports(
            user=request.user,
            sport_ids=serializer.validated_data["sports"]
        )

        return Response({"message": "Sports updated successfully"})