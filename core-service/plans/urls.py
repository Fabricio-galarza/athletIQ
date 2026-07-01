from django.urls import path
from plans.views.plan_view import PlanListCreateView, PlanDetailView
from plans.views.plan_feature_view import PlanFeatureView
from plans.views.feature_view import FeatureListCreateView, FeatureDetailView 
from plans.views.plan_module_view import PlanModuleView
from plans.views.plan_form_view import  PlanFormView               

urlpatterns = [
    # plans Urls
    path("plans/", PlanListCreateView.as_view()),
    path("plans/<uuid:pk>/", PlanDetailView.as_view()),
    path("plans/<uuid:pk>/features/", PlanFeatureView.as_view()),
    path("plans/<uuid:pk>/modules/", PlanModuleView.as_view()),
    path("plans/<uuid:pk>/forms/", PlanFormView.as_view()),
    
    # Features Urls
    path("features/", FeatureListCreateView.as_view()),
    path("features/<uuid:pk>/", FeatureDetailView.as_view()),
]