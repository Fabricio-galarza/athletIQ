from django.urls import path
from forms.views.form_view import (FormCreateView,FormUpdateView, FormToggleStatusView)
from forms.views.field_view import FieldCreateView
from forms.views.form_field_view import FormFieldConfigView
from forms.views.form_query_view import FormListView
from forms.views.field_option_view import FieldOptionConfigView
from forms.views.form_detail_view import FormDetailView

urlpatterns = [
    path('forms/', FormCreateView.as_view(), name='create-form'),
    path('forms/<uuid:form_id>/update/', FormUpdateView.as_view(), name='form-update'),
    path('forms/<uuid:form_id>/toggle-status/', FormToggleStatusView.as_view(), name='form-toggle-status'),
    path('fields/', FieldCreateView.as_view(), name='create-field'),
    path('forms/<uuid:form_id>/fields/', FormFieldConfigView.as_view(), name='form-fields-config'),
    path('form/get/', FormListView.as_view(), name='get-forms'),
    path('fields/<uuid:field_id>/options/', FieldOptionConfigView.as_view(), name='field-options'),
    path('forms/<uuid:form_id>/', FormDetailView.as_view(), name='form_detail'),
    
]