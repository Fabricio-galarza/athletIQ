# forms/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from forms.models import Form, FormField
from forms.serializers.form_by_id_serializer import FormResponseSerializer


class FormDetailView(APIView):
    """
    GET /api/v1/forms/{form_id}/?sport={sport_id}
    Returns a specific form with all its fields and options.
    Admin only.
    """
    permission_classes = [IsAdminUser]

    def get(self, request, form_id):
        sport_id = request.query_params.get("sport")

        try:
            # Get the form
            form = Form.objects.get(id=form_id, is_active=True)
            
            # Build response manually with fields and options
            result = {
                "id": str(form.id),
                "name": form.name,
                "code": form.code,
                "module": form.module.name if form.module else None,
                "is_active": form.is_active,
                "fields": []
            }
            
            # Get form fields ordered
            form_fields = form.form_fields.all().order_by('order')
            
            for ff in form_fields:
                field = ff.field
                
                # Build field data
                field_data = {
                    "id": str(field.id),
                    "name": field.name,
                    "label": ff.label or field.label,
                    "type": field.field_type.code if field.field_type else "text",
                    "required": ff.is_required,
                    "order": ff.order,
                }
                
                # Add options for select/radio/checkbox fields
                if field.field_type and field.field_type.code in ['select', 'radio', 'checkbox']:
                    options = field.options.all().order_by('order')
                    field_data["options"] = [
                        {
                            "value": opt.value,
                            "label": opt.label or opt.value,
                            "order": opt.order,
                        }
                        for opt in options
                    ]
                else:
                    field_data["options"] = []
                
                result["fields"].append(field_data)
            
            return Response(result, status=status.HTTP_200_OK)

        except Form.DoesNotExist:
            return Response(
                {"error": f"Form with id {form_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )