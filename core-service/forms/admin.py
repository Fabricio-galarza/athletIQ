from django.contrib import admin
from forms.models import Form, SportForm, DataType, FieldType, Field, FieldOPtion, FormField

# Register your models here.
admin.site.register(Form)
admin.site.register(SportForm)
admin.site.register(DataType)
admin.site.register(FieldType)
admin.site.register(Field)
admin.site.register(FieldOPtion)
admin.site.register(FormField)
