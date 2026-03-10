from django.urls import path
from . import views

app_name = 'training'

urlpatterns = [

    # ── Dashboard ──
    path('', views.TrainingSessionDashboardView.as_view(), name='dashboard'),

    # ── Training Topics (Master) ──
    path('topics/', views.TrainingTopicListView.as_view(), name='topic_list'),
    path('topics/create/', views.TrainingTopicCreateView.as_view(), name='topic_create'),
    path('topics/<int:pk>/edit/', views.TrainingTopicUpdateView.as_view(), name='topic_edit'),

    # ── Training Sessions ──
    path('sessions/', views.TrainingSessionListView.as_view(), name='session_list'),
    path('sessions/create/', views.TrainingSessionCreateView.as_view(), name='session_create'),
    path('sessions/<int:pk>/', views.TrainingSessionDetailView.as_view(), name='session_detail'),
    path('sessions/<int:pk>/edit/', views.TrainingSessionUpdateView.as_view(), name='session_edit'),
    path('sessions/<int:pk>/complete/', views.CompleteSessionView.as_view(), name='session_complete'),
    path('sessions/<int:pk>/cancel/', views.CancelSessionView.as_view(), name='session_cancel'),

    # ── Attendance ──
    path('sessions/<int:pk>/attendance/', views.MarkAttendanceView.as_view(), name='mark_attendance'),
    path('sessions/<int:pk>/participants/', views.AddParticipantsView.as_view(), name='add_participants'),

    # ── Training Records / Certificates ──
    path('records/', views.TrainingRecordListView.as_view(), name='record_list'),
    path('records/upload/', views.ManualCertificateUploadView.as_view(), name='manual_certificate'),

    # ── My Trainings (Employee view) ──
    path('my-trainings/', views.MyTrainingsView.as_view(), name='my_trainings'),

    # ── Compliance ──
    path('compliance/', views.TrainingComplianceView.as_view(), name='compliance'),

    # ── Notifications ──
    path('notifications/', views.TrainingNotificationListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/read/', views.MarkTrainingNotificationReadView.as_view(), name='notification_read'),
    path('notifications/read-all/', views.MarkAllTrainingNotificationsReadView.as_view(), name='notifications_read_all'),

    # ── AJAX ──
    path('ajax/get-zones/', views.TrainingGetZonesAjaxView.as_view(), name='ajax_get_zones'),
    path('ajax/get-locations/', views.TrainingGetLocationsAjaxView.as_view(), name='ajax_get_locations'),
    path('ajax/get-sublocations/', views.TrainingGetSublocationsAjaxView.as_view(), name='ajax_get_sublocations'),
    path('ajax/get-employees/', views.TrainingGetEmployeesAjaxView.as_view(), name='ajax_get_employees'),
]