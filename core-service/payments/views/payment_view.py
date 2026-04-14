from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from payments.serializers.payment_serializer import PaymentSerializer
from payments.services.payment_service import create_payment


class PaymentCreateView(APIView):

    # only authenticated users
    permission_classes = [IsAuthenticated]

    def post(self, request):
         
         # Validate input
         serializer = PaymentSerializer(data=request.data)

         if not serializer.is_valid():
              return Response(
                   serializer.errors,
                   status=status.HTTP_400_BAD_REQUEST
              )
         
         try:
              # Create payment using service
              payment = create_payment(
                   user=request.user,
                   validated_data=serializer.validated_data
              )
              # serializer response
              response_serializer = PaymentSerializer(payment)

              return Response(
                   response_serializer.data,
                   status=status.HTTP_201_CREATED
              )
         
         except ValueError as e:
              
              return Response(
                   {"error": str(e)},
                   status=status.HTTP_400_BAD_REQUEST
              )