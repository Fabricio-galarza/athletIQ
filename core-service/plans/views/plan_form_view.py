from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from plans.models import Plan, PlanForm
from plans.serializers.plan_form_serializer import PlanFormConfigSerializer
from plans.services.plan_form_service import set_plan_forms

class PlanFormView(APIView):

     # Only to admin users
    permission_classes = [IsAdminUser]
    
    def get_plan(self, pk):
        try:
            # Fetch plan by id
            return Plan.objects.get(pk=pk)
        except Plan.DoesNotExist:
            # Return None if not found
            return None

    def get(self, request, pk):

        # Get plan instance
        plan = self.get_plan(pk)

        # Handle not found
        if not plan:
            return Response({"error": "PLAN_NOT_FOUND"}, status=404)

        # Fetch related forms
        plan_forms = PlanForm.objects.filter(plan=plan)\
            .select_related("form")

        # Build response data
        data = [
            {
                "form_id": pf.form.id,
                "form_name": pf.form.name,
                "form_code": pf.form.code,
                "is_enabled": pf.is_enabled
            }
            for pf in plan_forms
        ]

        # Return list
        return Response(data)

    def put(self, request, pk):

        # Get plan instance
        plan = self.get_plan(pk)

        # Handle not found
        if not plan:
            return Response({"error": "PLAN_NOT_FOUND"}, status=404)

        # Validate input data
        serializer = PlanFormConfigSerializer(data=request.data, many=True)

        if serializer.is_valid():

            # Update plan forms
            set_plan_forms(plan, serializer.validated_data)

            return Response(
                {"message": "Forms updated successfully"}
            )

        # Return validation errors
        return Response(serializer.errors, status=400)