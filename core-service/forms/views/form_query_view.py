from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser

from forms.services.form_query_service import get_forms
from forms.serializers.form_response_serializer import FormResponseSerializer


class FormListView(APIView):

    permission_classes = [IsAdminUser]

    def get(self, request):

        module_code = request.query_params.get("module")
        sport_id = request.query_params.get("sport")

        forms = get_forms(
            module_code=module_code,
            user=request.user
        )

        serializer = FormResponseSerializer(
            forms,
            many=True,
            context={"sport_id": sport_id}
        )

        return Response(serializer.data)