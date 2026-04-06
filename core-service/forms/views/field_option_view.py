from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from forms.serializers.field_option_serializer import FieldOptionSerializer
from forms.services.field_option_service import set_field_options


class FieldOptionConfigView(APIView):

    permission_classes = [IsAuthenticated]

    def put(self, request, field_id):

        serializer = FieldOptionSerializer(data=request.data, many=True)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            options = set_field_options(
                field_id,
                serializer.validated_data
            )

            return Response(
                {
                    "message": "Options configured successfully",
                    "count": len(options)
                },
                status=status.HTTP_200_OK
            )

        except ValueError as e:
            return Response({"error": str(e)}, status=400)