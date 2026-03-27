from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from plans.models import Plan, PlanFeature
from plans.serializers.plan_feature_serializer import PlanFeatureConfigSerializer
from plans.services.plan_service import set_plan_features


class PlanFeatureView(APIView):

     # Only to admin users
    permission_classes = [IsAdminUser]

    # helper to get plan
    def get_plan(self, pk):
        print("BEFORE TRY")
        try:
            return Plan.objects.get(pk=pk)
        except Plan.DoesNotExist:
            return None
        
    # get all features for a plan
    def get(self, request, pk):
        print("IN GET")
        plan = self.get_plan(pk)

        if not plan:
            return Response(
                {"error": "PLAN_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND
            )

        plan_features = PlanFeature.objects.filter(plan=plan)\
            .select_related('feature')

        data = [
            {
                "feature_id": pf.feature.id,
                "feature_name": pf.feature.name,
                "feature_code": pf.feature.code,
                "is_enabled": pf.is_enabled
            }
            for pf in plan_features
        ]

        return Response(data, status=status.HTTP_200_OK)

    # configure features for a plan
    def put(self, request, pk):

        plan = self.get_plan(pk)

        if not plan:
            return Response(
                {"error": "PLAN_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = PlanFeatureConfigSerializer(data=request.data, many=True)

        if serializer.is_valid():

            set_plan_features(plan, serializer.validated_data)

            return Response(
                {"message": "Features updated successfully"},
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)