from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from forms.serializers.form_field_serializer import FormFieldSerializer
from forms.services.form_field_service import set_form_fields


class FormFieldConfigView(APIView):

    permission_classes = [IsAdminUser]

    def put(self, request, form_id):

        # get current user
        user = request.user

        # validate input (list of fields)
        serializer = FormFieldSerializer(data=request.data, many=True)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            form_fields = set_form_fields(form_id, serializer.validated_data, user)

            return Response(
                {
                    "message": "Form fields configured successfully",
                    "count": len(form_fields)
                },
                status=status.HTTP_200_OK
            )

        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )