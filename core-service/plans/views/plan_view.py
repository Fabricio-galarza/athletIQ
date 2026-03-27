from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from plans.models import Plan
from plans.serializers.plan_serializer import PlanSerializer
from plans.services.plan_service import create_plan,update_plan

# hadnles plan collection (list and create)
class PlanListCreateView(APIView):

     # Only to admin users
    permission_classes = [IsAdminUser]

    # return all plans
    def get(self, request):

        plans      = Plan.objects.all()
        serializer = PlanSerializer(plans, many = True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    
    # create a new plan
    def post(self, request):

        serializer = PlanSerializer(data=request.data)

        if serializer.is_valid():
            plan = create_plan(serializer.validated_data)

            return Response(
                PlanSerializer(plan).data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
# handles single plan (retrieve and update)
class PlanDetailView(APIView):

    # helper to get plan by id
    def get_object(self, pk):

        try:
            return Plan.objects.get(pk=pk)
        except Plan.DoesNotExist:
            return None

    # get plan detail
    def get(self, request, pk):

        plan = self.get_object(pk)

        if not plan:
            return Response(
                {"error": "PLAN_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = PlanSerializer(plan)

        return Response(serializer.data, status=status.HTTP_200_OK)

    # update plan
    def put(self, request, pk):

        plan = self.get_object(pk)

        if not plan:
            return Response(
                {"error": "PLAN_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = PlanSerializer(plan, data=request.data)

        if serializer.is_valid():
            updated_plan = update_plan(plan, serializer.validated_data)

            return Response(
                PlanSerializer(updated_plan).data,
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)