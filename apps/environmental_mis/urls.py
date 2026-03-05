from django.urls import path
from . import views

app_name = "environmental_mis"

urlpatterns = [

    # =====================================
    # BUSINESS TYPE
    # =====================================
    path("business-types/", views.business_type_list, name="business_type_list"),
    path("business-types/create/", views.business_type_create, name="business_type_create"),
    path("business-types/<int:pk>/edit/", views.business_type_edit, name="business_type_edit"),
    path("business-types/<int:pk>/delete/", views.business_type_delete, name="business_type_delete"),

    # =====================================
    # CONFIGURATION
    # =====================================
    path("configuration-list/", views.configuration_list, name="configuration_list"),
    path("configuration-flow/", views.configuration_flow, name="configuration_flow"),
    # REPORT CONFIGURATION
    path("report-config/", views.report_config_list, name="report_config_list"),
    path("report-config/create/", views.report_config_create, name="report_config_create"),
    path("report-config/<int:pk>/edit/", views.report_config_edit, name="report_config_edit"),
    path("report-config/<int:pk>/delete/", views.report_config_delete, name="report_config_delete"),

    # AJAX
    path("ajax/load-report-domains/", views.load_report_domains, name="load_report_domains"),
    path("ajax/load-report-categories/", views.load_report_categories, name="load_report_categories"),
    path("ajax/load-report-subcategories/",views.load_report_subcategories,name="load_report_subcategories"),
    path("ajax/load-report-units/", views.load_report_units, name="load_report_units"),

    #Reports
    path("manufacturing-environment-report/",views.manufacturing_environment_report,name="manufacturing_environment_report"),
    path("manufacturing-waste-report/",views.manufacturing_waste_report,name="manufacturing_waste_report"),
    path("save-manufacturing-waste/",views.save_manufacturing_waste,name="save_manufacturing_waste"),
    path("non-manufacturing-waste-report/",views.non_manufacturing_waste_report,name="non_manufacturing_waste_report")
]