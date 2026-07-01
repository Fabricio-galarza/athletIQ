# forms/views/form_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from forms.serializers.form_serializer import FormSerializer, FormUpdateSerializer
from forms.services.form_service import create_form, update_form, toggle_form_status


class FormCreateView(APIView):

    permission_classes = [IsAdminUser]

    def post(self, request):

        #get current user
        user       = request.user
        serializer = FormSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            form = create_form(serializer.validated_data, user)
            return Response(
                {
                    "message": "Form created successfully",
                    "data": {
                        "id": str(form.id),
                        "name": form.name,
                        "code": form.code,
                        "is_active": form.is_active
                    }
                },
                status=status.HTTP_201_CREATED
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# new View to update form
class FormUpdateView(APIView):

    permission_classes = [IsAdminUser]

    def put(self, request, form_id):
        """complete form updated"""
        serializer = FormUpdateSerializer(data=request.data)

        # get current user
        user = request.user
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            form = update_form(form_id, serializer.validated_data, user)
            return Response(
                {
                    "message": "Form updated successfully",
                    "data": {
                        "id": str(form.id),
                        "name": form.name,
                        "code": form.code,
                        "is_active": form.is_active
                    }
                },
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND
            )

    def patch(self, request, form_id):
        """partial updating form"""
        serializer = FormUpdateSerializer(
            data=request.data,
            partial=True  # Permite actualización parcial
        )
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            form = update_form(form_id, serializer.validated_data)
            return Response(
                {
                    "message": "Form updated successfully",
                    "data": {
                        "id": form.id,
                        "name": form.name,
                        "code": form.code,
                        "is_active": form.is_active
                    }
                },
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND
            )

class FormToggleStatusView(APIView):

    permission_classes = [IsAdminUser]

    def patch(self, request, form_id):

        # get current user
        user      = request.user
        is_active = request.data.get('is_active')
        
        if is_active is None:
            return Response(
                {"error": "is_active field is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not isinstance(is_active, bool):
            return Response(
                {"error": "is_active must be a boolean"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            form = toggle_form_status(form_id, is_active, user)
            status_text = "activated" if is_active else "deactivated"
            return Response(
                {
                    "message": f"Form {status_text} successfully",
                    "data": {
                        "id": str(form.id),
                        "name": form.name,
                        "code": form.code,
                        "is_active": form.is_active
                    }
                },
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND
            )