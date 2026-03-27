from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from plans.models import Plan, PlanModule
from plans.serializers.plan_module_serializer import PlanModuleConfigSerializer
from plans.services.plan_service import set_plan_modules


class PlanModuleView(APIView):

    def get_plan(self, pk):
        try:
            return Plan.objects.get(pk=pk)
        except Plan.DoesNotExist:
            return None

    # get modules assigned to a plan
    def get(self, request, pk):

        plan = self.get_plan(pk)

        if not plan:
            return Response(
                {"error": "PLAN_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND
            )

        plan_modules = PlanModule.objects.filter(plan=plan)\
            .select_related("module")

        data = [
            {
                "module_id": pm.module.id,
                "module_code": pm.module.code,
                "is_enabled": pm.is_enabled
            }
            for pm in plan_modules
        ]

        return Response(data, status=status.HTTP_200_OK)

    # configure modules for a plan
    def put(self, request, pk):

        plan = self.get_plan(pk)

        if not plan:
            return Response(
                {"error": "PLAN_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = PlanModuleConfigSerializer(data=request.data, many=True)

        if serializer.is_valid():

            set_plan_modules(plan, serializer.validated_data)

            return Response(
                {"message": "Modules updated successfully"},
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)