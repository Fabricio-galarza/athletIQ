from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from plans.models import Feature
from plans.serializers.feature_serializer import FeatureSerializer
from plans.services.feature_service import create_feature, update_feature


class FeatureListCreateView(APIView):

    # Only to admin users
    permission_classes = [IsAdminUser]
    
    def get(self, request):

        features = Feature.objects.all()
        serializer = FeatureSerializer(features, many=True)

        return Response(serializer.data)

    def post(self, request):

        serializer = FeatureSerializer(data=request.data)
        
        # get current user
        user = request.user
        
        if serializer.is_valid():
            feature = create_feature(serializer.validated_data, user)

            return Response(
                FeatureSerializer(feature).data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FeatureDetailView(APIView):

    def get_object(self, pk):

        try:
            return Feature.objects.get(pk=pk)
        except Feature.DoesNotExist:
            return None

    def get(self, request, pk):

        feature = self.get_object(pk)

        if not feature:
            return Response({"error": "FEATURE_NOT_FOUND"}, status=404)

        return Response(FeatureSerializer(feature).data)

    def put(self, request, pk):

        feature = self.get_object(pk)

        if not feature:
            return Response({"error": "FEATURE_NOT_FOUND"}, status=404)

        serializer = FeatureSerializer(feature, data=request.data)

        if serializer.is_valid():
            updated = update_feature(feature, serializer.validated_data)

            return Response(FeatureSerializer(updated).data)

        return Response(serializer.errors, status=400)