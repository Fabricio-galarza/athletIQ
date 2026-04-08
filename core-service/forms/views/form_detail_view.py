from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from forms.services.form_by_id_service import get_form_by_id
from forms.serializers.form_by_id_serializer import FormResponseSerializer


class FormDetailView(APIView):

    permission_classes = [IsAdminUser]

    def get(self, request, form_id):

        sport_id = request.query_params.get("sport")

        try:
            form = get_form_by_id(
                form_id=form_id,
                sport_id=sport_id,
                user=request.user
            )

            serializer = FormResponseSerializer(form)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )