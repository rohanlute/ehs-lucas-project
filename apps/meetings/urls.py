from django.urls import path
from . import views

app_name = 'meetings'

urlpatterns = [

    # ── Dashboard ──
    path('', views.meeting_dashboard, name='dashboard'),

    # ── Meeting CRUD ──
    path('list/', views.meeting_list, name='meeting_list'),
    path('create/', views.meeting_create, name='meeting_create'),
    path('<int:pk>/', views.meeting_detail, name='meeting_detail'),
    path('<int:pk>/edit/', views.meeting_edit, name='meeting_edit'),

    # ── Meeting workflow ──
    path('<int:pk>/complete/', views.meeting_complete, name='meeting_complete'),
    path('<int:pk>/cancel/', views.meeting_cancel, name='meeting_cancel'),
    path('<int:pk>/publish-mom/', views.publish_mom, name='publish_mom'),

    # ── Attendees ──
    path('<int:pk>/add-attendees/', views.add_attendees, name='add_attendees'),
    path('<int:pk>/mark-attendance/', views.mark_attendance, name='mark_attendance'),

    # ── Action Items ──
    path('<int:pk>/add-action/', views.add_action_item, name='add_action_item'),
    path('action/<int:action_pk>/close/', views.close_action_item, name='close_action_item'),
    path('action/<int:action_pk>/escalate/', views.escalate_to_hazard, name='escalate_to_hazard'),

    # ── My Meetings (employee view) ──
    path('my-meetings/', views.my_meetings, name='my_meetings'),

    # ── Notifications ──
    path('notifications/', views.notifications, name='notifications'),

    # ── AJAX ──
    path('ajax/get-zones/', views.ajax_get_zones, name='ajax_get_zones'),
    path('ajax/get-locations/', views.ajax_get_locations, name='ajax_get_locations'),
    path('ajax/get-sublocations/', views.ajax_get_sublocations, name='ajax_get_sublocations'),
    path('ajax/get-plant-employees/', views.ajax_get_plant_employees, name='ajax_get_plant_employees'),
]