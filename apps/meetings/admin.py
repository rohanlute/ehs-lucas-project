from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import SafetyMeeting, MeetingAttendee, MeetingActionItem, MeetingNotification


# ============================================================
# INLINE — Attendees inside SafetyMeeting admin
# ============================================================

class MeetingAttendeeInline(admin.TabularInline):
    model = MeetingAttendee
    fk_name = 'meeting'
    extra = 0
    fields = ('employee', 'attendance_status', 'signed', 'marked_by', 'marked_at', 'remarks')
    readonly_fields = ('marked_by', 'marked_at')
    autocomplete_fields = ['employee']


# ============================================================
# INLINE — Action Items inside SafetyMeeting admin
# ============================================================

class MeetingActionItemInline(admin.TabularInline):
    model = MeetingActionItem
    fk_name = 'meeting' 
    extra = 0
    fields = ('description', 'priority', 'assigned_to', 'due_date', 'status', 'escalated_to_hazard')
    readonly_fields = ('escalated_to_hazard',)


# ============================================================
# SAFETY MEETING ADMIN
# ============================================================

@admin.register(SafetyMeeting)
class SafetyMeetingAdmin(admin.ModelAdmin):

    list_display  = (
        'meeting_number', 'title', 'meeting_type_badge',
        'plant', 'scheduled_date', 'chairperson',
        'status_badge', 'attendance_summary', 'open_actions_count', 'mom_status',
    )
    list_filter   = ('status', 'meeting_type', 'plant', 'scheduled_date', 'mom_published')
    search_fields = ('meeting_number', 'title', 'chairperson__first_name', 'chairperson__last_name')
    readonly_fields = (
        'meeting_number', 'created_by', 'created_at', 'updated_at',
        'mom_published_at',
    )
    date_hierarchy = 'scheduled_date'

    inlines = [MeetingAttendeeInline, MeetingActionItemInline]

    fieldsets = (
        ('Meeting Info', {
            'fields': (
                'meeting_number', 'title', 'meeting_type', 'status',
            )
        }),
        ('Location', {
            'fields': ('plant', 'zone', 'location', 'sublocation', 'venue_details')
        }),
        ('Schedule', {
            'fields': ('scheduled_date', 'scheduled_time', 'end_time', 'chairperson')
        }),
        ('Agenda', {
            'fields': ('agenda', 'agenda_attachment')
        }),
        ('Minutes of Meeting', {
            'fields': (
                'actual_date', 'actual_start_time', 'actual_end_time',
                'minutes_of_meeting', 'mom_attachment',
                'mom_published', 'mom_published_at',
            ),
            'classes': ('collapse',),
        }),
        ('Cancellation', {
            'fields': ('cancelled_reason',),
            'classes': ('collapse',),
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # ── Custom display methods ──

    def status_badge(self, obj):
        colors = {
            'SCHEDULED':   'info',
            'IN_PROGRESS': 'warning',
            'COMPLETED':   'success',
            'CANCELLED':   'danger',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def meeting_type_badge(self, obj):
        colors = {
            'SAFETY_COMMITTEE': 'primary',
            'TOOLBOX_TALK':     'info',
            'DEPARTMENTAL':     'secondary',
            'EMERGENCY':        'danger',
            'MONTHLY_REVIEW':   'success',
            'INCIDENT_REVIEW':  'warning',
            'AUDIT_REVIEW':     'dark',
            'CUSTOM':           'light',
        }
        color = colors.get(obj.meeting_type, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_meeting_type_display()
        )
    meeting_type_badge.short_description = 'Type'

    def attendance_summary(self, obj):
        total   = obj.total_invited
        present = obj.total_present
        pct     = obj.attendance_percentage
        if total == 0:
            return format_html('<span class="text-muted">No attendees</span>')
        color = 'success' if pct >= 75 else 'warning' if pct >= 50 else 'danger'
        return format_html(
            '<span class="text-{}">{}/{} ({}%)</span>',
            color, present, total, pct
        )
    attendance_summary.short_description = 'Attendance'

    def open_actions_count(self, obj):
        count = obj.open_action_items_count
        if count == 0:
            return format_html('<span class="text-success">✓ None</span>')
        return format_html('<span class="text-warning font-weight-bold">{} Open</span>', count)
    open_actions_count.short_description = 'Open Actions'

    def mom_status(self, obj):
        if obj.status != 'COMPLETED':
            return '—'
        if obj.mom_published:
            return format_html('<span class="text-success">✓ Published</span>')
        return format_html('<span class="text-warning">Pending</span>')
    mom_status.short_description = 'MOM'


# ============================================================
# MEETING ATTENDEE ADMIN
# ============================================================

@admin.register(MeetingAttendee)
class MeetingAttendeeAdmin(admin.ModelAdmin):

    list_display  = ('meeting', 'employee', 'attendance_badge', 'signed', 'marked_by', 'marked_at')
    list_filter   = ('attendance_status', 'signed', 'meeting__plant', 'meeting__status')
    search_fields = (
        'employee__first_name', 'employee__last_name',
        'meeting__meeting_number', 'meeting__title',
    )
    readonly_fields = ('marked_by', 'marked_at', 'created_at', 'updated_at')

    def attendance_badge(self, obj):
        colors = {
            'INVITED': 'secondary',
            'PRESENT': 'success',
            'ABSENT':  'danger',
            'ONLINE':  'info',
        }
        color = colors.get(obj.attendance_status, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_attendance_status_display()
        )
    attendance_badge.short_description = 'Attendance'


# ============================================================
# MEETING ACTION ITEM ADMIN
# ============================================================

@admin.register(MeetingActionItem)
class MeetingActionItemAdmin(admin.ModelAdmin):

    list_display  = (
        'meeting', 'description_short', 'priority_badge',
        'assigned_to', 'due_date', 'status_badge',
        'overdue_flag', 'escalated_to_hazard',
    )
    list_filter   = ('status', 'priority', 'escalated_to_hazard', 'meeting__plant')
    search_fields = ('description', 'meeting__meeting_number', 'assigned_to__first_name')
    readonly_fields = ('assigned_by', 'closed_by', 'closed_at', 'created_at', 'updated_at')
    date_hierarchy = 'due_date'

    fieldsets = (
        ('Action Item', {
            'fields': ('meeting', 'description', 'priority', 'assigned_to', 'assigned_by', 'due_date', 'status')
        }),
        ('Closure', {
            'fields': ('closure_remarks', 'closure_attachment', 'closed_by', 'closed_at'),
            'classes': ('collapse',),
        }),
        ('Hazard Link', {
            'fields': ('hazard_report', 'escalated_to_hazard'),
            'classes': ('collapse',),
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def description_short(self, obj):
        return obj.description[:60] + '...' if len(obj.description) > 60 else obj.description
    description_short.short_description = 'Description'

    def priority_badge(self, obj):
        colors = {
            'LOW':    'secondary',
            'MEDIUM': 'info',
            'HIGH':   'warning',
            'URGENT': 'danger',
        }
        color = colors.get(obj.priority, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'

    def status_badge(self, obj):
        colors = {
            'OPEN':        'danger',
            'IN_PROGRESS': 'warning',
            'CLOSED':      'success',
            'CANCELLED':   'secondary',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def overdue_flag(self, obj):
        if obj.is_overdue:
            return format_html(
                '<span class="text-danger font-weight-bold">⚠ {} days overdue</span>',
                obj.days_overdue
            )
        return format_html('<span class="text-success">On Track</span>')
    overdue_flag.short_description = 'Overdue'


# ============================================================
# MEETING NOTIFICATION ADMIN
# ============================================================

@admin.register(MeetingNotification)
class MeetingNotificationAdmin(admin.ModelAdmin):

    list_display  = ('recipient', 'notification_type_badge', 'title', 'meeting', 'is_read', 'created_at')
    list_filter   = ('notification_type', 'is_read', 'meeting__plant')
    search_fields = ('recipient__first_name', 'recipient__last_name', 'title')
    readonly_fields = ('created_at', 'read_at')

    def notification_type_badge(self, obj):
        colors = {
            'MEETING_SCHEDULED':   'primary',
            'MEETING_REMINDER':    'info',
            'MEETING_CANCELLED':   'danger',
            'MEETING_RESCHEDULED': 'warning',
            'ATTENDANCE_MARKED':   'success',
            'MOM_PUBLISHED':       'success',
            'ACTION_ASSIGNED':     'warning',
            'ACTION_DUE_SOON':     'warning',
            'ACTION_OVERDUE':      'danger',
            'ACTION_CLOSED':       'success',
            'ESCALATED_TO_HAZARD': 'danger',
        }
        color = colors.get(obj.notification_type, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_notification_type_display()
        )
    notification_type_badge.short_description = 'Type'