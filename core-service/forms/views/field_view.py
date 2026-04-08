from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from forms.serializers.field_serializer import FieldSerializer
from forms.services.field_service import create_field


class FieldCreateView(APIView):

    # require authentication
    permission_classes = [IsAuthenticated]

    def post(self, request):

        # validate request data
        serializer = FieldSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # call service
            field = create_field(serializer.validated_data)

            return Response(
                {
                    "message": "Field created successfully",
                    "data": {
                        "id": field.id,
                        "name": field.name,
                        "field_type": field.field_type.code,
                        "data_type": field.data_type.code
                    }
                },
                status=status.HTTP_201_CREATED
            )

        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )