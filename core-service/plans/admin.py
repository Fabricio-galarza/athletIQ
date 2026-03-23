from django.contrib import admin
from plans.models import Plan, Feature, UserPlan, PlanFeature

admin.site.register(Plan)
admin.site.register(Feature)
admin.site.register(UserPlan)
admin.site.register(PlanFeature)
