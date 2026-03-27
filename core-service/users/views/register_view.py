from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from users.serializers.register_serializers import RegisterSerializer
from users.services.register_user import register_user


class RegisterView(APIView):

     # used to end point public
    permission_classes = [AllowAny] 
    def post(self, request):

        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "error": "ERROR DE VALIDACIÓN",
                    "details": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            result = register_user(serializer.validated_data)

            return Response(
                {
                    "id": result["id"],
                    "email": result["email"],
                    "profile": {
                        "first_name": result["first_name"],
                        "last_name": result["last_name"],
                    },
                    "role": result["role"],
                    "plan": result["plan"],
                    "message": "Usuario registrado exitosamente"
                },
                status=status.HTTP_201_CREATED
            )

        except ValueError as e:
            return Response(
                {
                    "error": str(e),
                    "message": "El usuario ya está registrado"
                },
                status=status.HTTP_409_CONFLICT
            )