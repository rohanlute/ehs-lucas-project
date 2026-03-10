from django.urls import path
from . import views

app_name = "environmental_mis"

urlpatterns = [

    # Waste Reports
    path("manufacturing-waste-report/",views.manufacturing_waste_report,name="manufacturing_waste_report"),
    path("save-waste-report/",views.save_waste_report,name="save_waste_report"),

    # Environment Reports
    path("environment-report/",views.environment_report,name="environment_report"),
    path("save-environment-report/",views.save_environment_report,name="save_environment_report"),

    #Leading Indicator
    # path("leading-indicator/",views.leading_indicator,name="leading_indicator"),
    # path("save-leading-indicator/",views.save_leading_indicator,name="save_leading_indicator)

    #Analytical Dashboard
    path("environment-dashboard/",views.environment_dashboard,name="environment_dashboard"),
    path("waste-dashboard/",views.waste_dashboard,name="waste_dashboard"),
]