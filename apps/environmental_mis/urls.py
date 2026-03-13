from django.urls import path
from . import views

app_name = "environmental_mis"

urlpatterns = [

    # Waste Reports
    path("manufacturing-waste-report/",views.manufacturing_waste_report,name="manufacturing_waste_report"),
    path("save-waste-report/",views.save_waste_report,name="save_waste_report"),
    path("download-waste-excel/",views.download_waste_excel,name="download_waste_excel"),

    # Environment Reports
    path("environment-report/",views.environment_report,name="environment_report"),
    path("save-environment-report/",views.save_environment_report,name="save_environment_report"),
    path("download-environment-excel/",views.download_environment_excel,name="download_environment_excel"),

    #Leading Indicator
    path("safety-indicator/",views.safety_indicator,name="safety_indicator"),
    path("save-safety-indicator/",views.save_safety_indicator,name="save_safety_indicator"),
    path("download-safety-excel/",views.download_safety_excel,name="download_safety_excel"),

    #Analytical Dashboard
    path("environment-dashboard/",views.environment_dashboard,name="environment_dashboard"),
    path("waste-dashboard/",views.waste_dashboard,name="waste_dashboard"),
    path("safety-dashboard/",views.safety_dashboard,name="safety_dashboard"),



]