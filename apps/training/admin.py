from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    TrainingTopic,
    TrainingRequirement,
    TrainingSession,
    TrainingParticipant,
    TrainingRecord,
    TrainingNotification,
)


# ============================================================
# 1. TRAINING TOPIC
# ============================================================

@admin.register(TrainingTopic)
class TrainingTopicAdmin(admin.ModelAdmin):
    list_display  = (
        'name', 'code', 'category_badge', 'validity_period_days',
        'passing_score', 'mandatory_badge', 'is_active', 'created_at',
    )
    list_filter   = ('category', 'is_mandatory', 'is_active')
    search_fields = ('name', 'code', 'description')
    ordering      = ('name',)
    readonly_fields = ('created_at', 'updated_at', 'created_by')

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'code', 'category', 'description'),
        }),
        ('Assessment & Validity', {
            'fields': ('validity_period_days', 'passing_score'),
        }),
        ('Settings', {
            'fields': ('is_mandatory', 'is_active'),
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def category_badge(self, obj):
        return format_html(
            '<span style="background:#17a2b8;color:#fff;padding:2px 8px;border-radius:10px;font-size:0.8em;">{}</span>',
            obj.get_category_display()
        )
    category_badge.short_description = 'Category'

    def mandatory_badge(self, obj):
        if obj.is_mandatory:
            return format_html('<span style="color:#dc3545;font-weight:bold;">● Mandatory</span>')
        return format_html('<span style="color:#6c757d;">○ Optional</span>')
    mandatory_badge.short_description = 'Mandatory'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ============================================================
# 2. TRAINING REQUIREMENT
# ============================================================

@admin.register(TrainingRequirement)
class TrainingRequirementAdmin(admin.ModelAdmin):
    list_display  = ('topic', 'applicable_to', 'role', 'department', 'plant', 'due_within_days')
    list_filter   = ('applicable_to', 'topic')
    search_fields = ('topic__name', 'role__name', 'department__name', 'plant__name')
    ordering      = ('topic__name',)
    readonly_fields = ('created_at', 'created_by')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ============================================================
# 3. TRAINING PARTICIPANT (Inline for Session)
# ============================================================

class TrainingParticipantInline(admin.TabularInline):
    model   = TrainingParticipant
    extra   = 0
    fields  = (
        'employee', 'attendance_status', 'assessment_score',
        'passed', 'remarks', 'marked_by', 'marked_at',
    )
    readonly_fields = ('passed', 'marked_at')
    show_change_link = False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('employee', 'marked_by')


# ============================================================
# 4. TRAINING SESSION
# ============================================================

@admin.register(TrainingSession)
class TrainingSessionAdmin(admin.ModelAdmin):
    list_display = (
        'session_number', 'topic', 'training_mode',
        'scheduled_date', 'plant', 'trainer_name',
        'status_badge', 'total_invited_display', 'total_present_display',
        'is_overdue_display',
    )
    list_filter  = ('status', 'training_mode', 'plant', 'topic__category', 'scheduled_date')
    search_fields = (
        'session_number', 'topic__name', 'trainer_name',
        'plant__name', 'location__name',
    )
    ordering      = ('-scheduled_date',)
    readonly_fields = (
        'session_number', 'created_by', 'created_at', 'updated_at',
        'total_invited_display', 'total_present_display', 'attendance_percentage_display',
    )
    date_hierarchy = 'scheduled_date'
    inlines       = [TrainingParticipantInline]

    fieldsets = (
        ('Session Info', {
            'fields': ('session_number', 'topic', 'training_mode', 'status'),
        }),
        ('Schedule', {
            'fields': ('scheduled_date', 'scheduled_time', 'end_time', 'duration_hours'),
        }),
        ('Location', {
            'fields': ('plant', 'zone', 'location', 'sublocation', 'venue_details'),
        }),
        ('Trainer', {
            'fields': (
                'trainer_name', 'trainer_designation',
                'trainer_is_external', 'trainer_organization',
            ),
        }),
        ('Session Details', {
            'fields': ('agenda', 'max_participants', 'remarks', 'attachment'),
        }),
        ('Completion Info', {
            'fields': ('actual_date', 'completion_remarks', 'completion_attachment'),
            'classes': ('collapse',),
        }),
        ('Cancellation', {
            'fields': ('cancelled_reason',),
            'classes': ('collapse',),
        }),
        ('Attendance Summary', {
            'fields': (
                'total_invited_display',
                'total_present_display',
                'attendance_percentage_display',
            ),
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'SCHEDULED':  '#ffc107',
            'ONGOING':    '#17a2b8',
            'COMPLETED':  '#28a745',
            'CANCELLED':  '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:10px;font-size:0.8em;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def total_invited_display(self, obj):
        return obj.total_invited
    total_invited_display.short_description = 'Invited'

    def total_present_display(self, obj):
        return obj.total_present
    total_present_display.short_description = 'Present'

    def attendance_percentage_display(self, obj):
        pct = obj.attendance_percentage
        color = '#28a745' if pct >= 80 else '#ffc107' if pct >= 50 else '#dc3545'
        return format_html(
            '<strong style="color:{};">{}%</strong>', color, pct
        )
    attendance_percentage_display.short_description = 'Attendance %'

    def is_overdue_display(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color:#dc3545;font-weight:bold;">⚠ Overdue</span>')
        return '—'
    is_overdue_display.short_description = 'Overdue'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ============================================================
# 5. TRAINING PARTICIPANT (Standalone)
# ============================================================

@admin.register(TrainingParticipant)
class TrainingParticipantAdmin(admin.ModelAdmin):
    list_display  = (
        'session', 'employee', 'attendance_status_badge',
        'assessment_score', 'passed_badge', 'marked_by', 'marked_at',
    )
    list_filter   = ('attendance_status', 'passed', 'session__plant', 'session__topic')
    search_fields = (
        'employee__first_name', 'employee__last_name',
        'employee__employee_id', 'session__session_number',
    )
    ordering      = ('-session__scheduled_date', 'employee__first_name')
    readonly_fields = ('passed', 'marked_at', 'created_at', 'updated_at')

    def attendance_status_badge(self, obj):
        colors = {
            'INVITED': '#6c757d',
            'PRESENT': '#28a745',
            'ABSENT':  '#dc3545',
            'PARTIAL': '#ffc107',
        }
        color = colors.get(obj.attendance_status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:0.8em;">{}</span>',
            color, obj.get_attendance_status_display()
        )
    attendance_status_badge.short_description = 'Attendance'

    def passed_badge(self, obj):
        if obj.passed is None:
            return format_html('<span style="color:#6c757d;">—</span>')
        if obj.passed:
            return format_html('<span style="color:#28a745;font-weight:bold;">✓ Pass</span>')
        return format_html('<span style="color:#dc3545;font-weight:bold;">✗ Fail</span>')
    passed_badge.short_description = 'Result'


# ============================================================
# 6. TRAINING RECORD
# ============================================================

@admin.register(TrainingRecord)
class TrainingRecordAdmin(admin.ModelAdmin):
    list_display  = (
        'certificate_number', 'employee', 'topic',
        'completed_date', 'valid_until', 'expiry_status_badge',
        'status_badge', 'added_manually',
    )
    list_filter   = ('status', 'added_manually', 'topic', 'topic__category')
    search_fields = (
        'certificate_number', 'employee__first_name', 'employee__last_name',
        'employee__employee_id', 'topic__name',
    )
    ordering      = ('-completed_date',)
    readonly_fields = (
        'certificate_number', 'created_by', 'created_at', 'updated_at',
        'expiry_status_badge', 'days_until_expiry_display',
    )
    date_hierarchy = 'completed_date'

    fieldsets = (
        ('Certificate Info', {
            'fields': ('certificate_number', 'employee', 'topic', 'session'),
        }),
        ('Dates', {
            'fields': ('completed_date', 'valid_until'),
        }),
        ('Status', {
            'fields': (
                'status', 'added_manually',
                'expiry_status_badge', 'days_until_expiry_display',
            ),
        }),
        ('Files', {
            'fields': ('certificate_file',),
        }),
        ('Revocation', {
            'fields': ('revoked_reason',),
            'classes': ('collapse',),
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'ACTIVE':   '#28a745',
            'EXPIRED':  '#dc3545',
            'REVOKED':  '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:0.8em;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def expiry_status_badge(self, obj):
        days  = obj.days_until_expiry
        if days < 0:
            return format_html('<span style="color:#dc3545;font-weight:bold;">Expired</span>')
        elif days <= 7:
            return format_html('<span style="color:#dc3545;">Critical — {}d left</span>', days)
        elif days <= 30:
            return format_html('<span style="color:#fd7e14;">Expiring — {}d left</span>', days)
        elif days <= 60:
            return format_html('<span style="color:#ffc107;">Warning — {}d left</span>', days)
        return format_html('<span style="color:#28a745;">Active — {}d left</span>', days)
    expiry_status_badge.short_description = 'Expiry Status'

    def days_until_expiry_display(self, obj):
        return f"{obj.days_until_expiry} days"
    days_until_expiry_display.short_description = 'Days Until Expiry'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ============================================================
# 7. TRAINING NOTIFICATION
# ============================================================

@admin.register(TrainingNotification)
class TrainingNotificationAdmin(admin.ModelAdmin):
    list_display  = (
        'recipient', 'notification_type_badge',
        'title', 'is_read', 'created_at', 'read_at',
    )
    list_filter   = ('notification_type', 'is_read')
    search_fields = ('recipient__first_name', 'recipient__last_name', 'title', 'message')
    ordering      = ('-created_at',)
    readonly_fields = ('created_at', 'read_at')

    def notification_type_badge(self, obj):
        colors = {
            'SESSION_SCHEDULED':  '#007bff',
            'SESSION_REMINDER':   '#17a2b8',
            'SESSION_CANCELLED':  '#dc3545',
            'ATTENDANCE_MARKED':  '#6c757d',
            'CERTIFICATE_ISSUED': '#28a745',
            'EXPIRY_ALERT_60':    '#ffc107',
            'EXPIRY_ALERT_30':    '#fd7e14',
            'EXPIRY_ALERT_7':     '#dc3545',
            'CERTIFICATE_EXPIRED':'#dc3545',
            'TRAINING_OVERDUE':   '#dc3545',
        }
        color = colors.get(obj.notification_type, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:0.75em;">{}</span>',
            color, obj.get_notification_type_display()
        )
    notification_type_badge.short_description = 'Type'