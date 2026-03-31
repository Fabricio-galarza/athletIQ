from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from users.serializers.login_serializers import LoginSerizalizer
from users.services.login_user import login_user




class LoginView(APIView):

    # used to end point public
    permission_classes = [AllowAny]
    
    def post(self, request):

        # 🔹 validate incoming data structure with serializer
        serializer = LoginSerizalizer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "error": "CREDENCIALES INVÁLIDAS",
                    "details": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔹 attempt login and return full session data
        try:
            result = login_user(serializer.validated_data)
           
            return Response(
                {
                    # quick access token for immediate use
                    "token": result["tokens"]["access"],
                    "user": {
                        "id": result["user"]["id"],
                        "email": result["user"]["email"],
                    },
                    "roles": result["roles"],
                    "plans": result["plans"],
                    "features": result["features"],
                    "sports": result["sports"],
                    "forms": result["forms"],
                    # full token pair so frontend can handle refresh flow
                    "tokens": result["tokens"],
                    "message": "Inicio de sesión exitoso"
                },
                status=status.HTTP_200_OK
            )

        # 🔹 invalid credentials raised from login_user
        except ValueError as e:
            return Response(
                {
                    "error": str(e),
                    "message": "Credenciales inválidas"
                },
                status=status.HTTP_409_CONFLICT
            )