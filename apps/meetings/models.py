import datetime
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.organizations.models import Plant, Zone, Location, SubLocation, Department

User = get_user_model()


# ============================================================
# 1. SAFETY MEETING (Main model — like Incident)
# ============================================================

class SafetyMeeting(models.Model):

    MEETING_TYPE_CHOICES = [
        ('SAFETY_COMMITTEE',  'Safety Committee Meeting'),
        ('TOOLBOX_TALK',      'Toolbox Talk'),
        ('DEPARTMENTAL',      'Departmental Safety Meeting'),
        ('EMERGENCY',         'Emergency Meeting'),
        ('MONTHLY_REVIEW',    'Monthly Safety Review'),
        ('INCIDENT_REVIEW',   'Incident Review Meeting'),
        ('AUDIT_REVIEW',      'Audit Review Meeting'),
        ('CUSTOM',            'Other / Custom'),
    ]

    STATUS_CHOICES = [
        ('SCHEDULED',    'Scheduled'),
        ('IN_PROGRESS',  'In Progress'),
        ('COMPLETED',    'Completed'),
        ('CANCELLED',    'Cancelled'),
    ]

    # Auto-generated: SM-{PLANT_CODE}-{YYYYMMDD}-{001}
    # Same pattern as your report_number / session_number
    meeting_number  = models.CharField(max_length=50, unique=True, editable=False)

    title           = models.CharField(max_length=300)
    meeting_type    = models.CharField(max_length=30, choices=MEETING_TYPE_CHOICES, default='SAFETY_COMMITTEE')

    # ── Same location chain as Incident / TrainingSession ──
    plant           = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name='safety_meetings')
    zone            = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='safety_meetings')
    location        = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='safety_meetings')
    sublocation     = models.ForeignKey(SubLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='safety_meetings')
    venue_details   = models.CharField(max_length=255, blank=True, help_text="e.g. Conference Room A, Gate 2 Office")

    # ── Schedule ──
    scheduled_date  = models.DateField()
    scheduled_time  = models.TimeField()
    end_time        = models.TimeField(null=True, blank=True)
    duration_minutes= models.PositiveIntegerField(null=True, blank=True)

    # ── Chairperson (who chairs the meeting) ──
    # Safety Officer or HOD chairs the meeting
    chairperson     = models.ForeignKey(
                        User, on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='chaired_meetings',
                        help_text="Person who will chair/conduct this meeting"
                      )

    # ── Pre-meeting ──
    agenda          = models.TextField(blank=True, help_text="Meeting agenda / topics to be discussed")
    agenda_attachment = models.FileField(
                        upload_to='meeting_agendas/%Y/%m/',
                        null=True, blank=True,
                        help_text="Upload agenda document (PDF/Word)"
                      )

    # ── Workflow ──
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    cancelled_reason= models.TextField(blank=True)

    # ── Post-meeting (filled when completing the meeting) ──
    actual_date             = models.DateField(null=True, blank=True)
    actual_start_time       = models.TimeField(null=True, blank=True)
    actual_end_time         = models.TimeField(null=True, blank=True)
    minutes_of_meeting      = models.TextField(
                                blank=True,
                                help_text="Full minutes of the meeting — what was discussed, decisions taken"
                              )
    mom_attachment          = models.FileField(
                                upload_to='meeting_minutes/%Y/%m/',
                                null=True, blank=True,
                                help_text="Upload signed MOM document"
                              )
    mom_published           = models.BooleanField(
                                default=False,
                                help_text="When True, all attendees are notified with the MOM"
                              )
    mom_published_at        = models.DateTimeField(null=True, blank=True)

    # ── Standard audit fields ──
    created_by      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='safety_meetings_created')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date', '-scheduled_time']
        verbose_name = 'Safety Meeting'
        verbose_name_plural = 'Safety Meetings'

    def __str__(self):
        return f"{self.meeting_number} - {self.title}"

    def save(self, *args, **kwargs):
        # Auto-generate meeting_number like your report_number pattern
        if not self.meeting_number:
            today = datetime.date.today()
            date_str = today.strftime('%Y%m%d')
            plant_code = self.plant.code if self.plant else 'XXX'

            count = SafetyMeeting.objects.filter(
                meeting_number__contains=f'SM-{plant_code}-{date_str}'
            ).count()

            self.meeting_number = f'SM-{plant_code}-{date_str}-{count + 1:03d}'

        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        """Scheduled but not completed past its date"""
        if self.status == 'SCHEDULED' and self.scheduled_date:
            return datetime.date.today() > self.scheduled_date
        return False

    @property
    def total_invited(self):
        return self.attendees.count()

    @property
    def total_present(self):
        return self.attendees.filter(attendance_status='PRESENT').count()

    @property
    def attendance_percentage(self):
        if self.total_invited == 0:
            return 0
        return round((self.total_present / self.total_invited) * 100, 1)

    @property
    def open_action_items_count(self):
        return self.action_items.filter(status__in=['OPEN', 'IN_PROGRESS']).count()

    @property
    def can_be_completed(self):
        """Check if meeting can be marked as completed"""
        if self.status == 'COMPLETED':
            return False, "Meeting is already completed"
        if self.status == 'CANCELLED':
            return False, "Cancelled meeting cannot be completed"
        if self.attendees.count() == 0:
            return False, "No attendees added to this meeting"
        return True, "Ready to complete"


# ============================================================
# 2. MEETING ATTENDEE
#    Like TrainingParticipant — per employee per meeting
# ============================================================

class MeetingAttendee(models.Model):

    ATTENDANCE_STATUS_CHOICES = [
        ('INVITED',  'Invited'),
        ('PRESENT',  'Present'),
        ('ABSENT',   'Absent'),
        ('ONLINE',   'Attended Online'),   # for virtual attendees
    ]

    meeting             = models.ForeignKey(SafetyMeeting, on_delete=models.CASCADE, related_name='attendees')
    employee            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meeting_attendances')

    attendance_status   = models.CharField(max_length=10, choices=ATTENDANCE_STATUS_CHOICES, default='INVITED')

    # Physical signature collected on attendance sheet
    signed              = models.BooleanField(
                            default=False,
                            help_text="Has the attendee physically signed the attendance register?"
                          )

    remarks             = models.TextField(blank=True)

    # Who marked the attendance
    marked_by           = models.ForeignKey(
                            User, on_delete=models.SET_NULL,
                            null=True, blank=True,
                            related_name='meeting_attendance_marked'
                          )
    marked_at           = models.DateTimeField(null=True, blank=True)

    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['employee__first_name']
        # One employee can only appear once per meeting
        unique_together = ('meeting', 'employee')
        verbose_name = 'Meeting Attendee'
        verbose_name_plural = 'Meeting Attendees'

    def __str__(self):
        return f"{self.meeting.meeting_number} - {self.employee.get_full_name()}"


# ============================================================
# 3. MEETING ACTION ITEM
#    Raised during the meeting — like HazardActionItem
#    Can optionally be escalated to a Hazard Report
# ============================================================

class MeetingActionItem(models.Model):

    PRIORITY_CHOICES = [
        ('LOW',    'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH',   'High'),
        ('URGENT', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('OPEN',        'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('CLOSED',      'Closed'),
        ('CANCELLED',   'Cancelled'),
    ]

    meeting         = models.ForeignKey(SafetyMeeting, on_delete=models.CASCADE, related_name='action_items')

    # ── Action item details ──
    description     = models.TextField(help_text="What action needs to be taken?")
    priority        = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    due_date        = models.DateField()

    # ── Assignment ──
    assigned_to     = models.ForeignKey(
                        User, on_delete=models.SET_NULL,
                        null=True,
                        related_name='meeting_action_items_assigned'
                      )
    assigned_by     = models.ForeignKey(
                        User, on_delete=models.SET_NULL,
                        null=True,
                        related_name='meeting_action_items_raised'
                      )

    # ── Workflow ──
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='OPEN')

    # ── Closure ──
    closure_remarks = models.TextField(blank=True)
    closure_attachment = models.FileField(
                          upload_to='meeting_action_closures/%Y/%m/',
                          null=True, blank=True
                        )
    closed_by       = models.ForeignKey(
                        User, on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='meeting_action_items_closed'
                      )
    closed_at       = models.DateTimeField(null=True, blank=True)

    # ── Hazard Module Link ──
    # When action item is serious, Safety Officer can escalate to a Hazard Report
    # FK to hazards.HazardReport — using string reference to avoid circular imports
    hazard_report   = models.ForeignKey(
                        'hazards.Hazard',
                        on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='meeting_action_items',
                        help_text="If this action was escalated to a Hazard Report, link it here"
                      )
    escalated_to_hazard = models.BooleanField(
                            default=False,
                            help_text="True when this action item has been converted to a Hazard Report"
                          )

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'due_date']
        verbose_name = 'Meeting Action Item'
        verbose_name_plural = 'Meeting Action Items'

    def __str__(self):
        return f"Action [{self.get_priority_display()}] - {self.meeting.meeting_number}"

    @property
    def is_overdue(self):
        if self.status in ['OPEN', 'IN_PROGRESS'] and self.due_date:
            return datetime.date.today() > self.due_date
        return False

    @property
    def days_overdue(self):
        if self.is_overdue:
            return (datetime.date.today() - self.due_date).days
        return 0


# ============================================================
# 4. MEETING NOTIFICATION
#    Exactly like TrainingNotification / IncidentNotification
# ============================================================

class MeetingNotification(models.Model):

    NOTIFICATION_TYPES = [
        ('MEETING_SCHEDULED',    'Meeting Scheduled'),
        ('MEETING_REMINDER',     'Meeting Reminder (1 day before)'),
        ('MEETING_CANCELLED',    'Meeting Cancelled'),
        ('MEETING_RESCHEDULED',  'Meeting Rescheduled'),
        ('ATTENDANCE_MARKED',    'Attendance Marked'),
        ('MOM_PUBLISHED',        'Minutes of Meeting Published'),
        ('ACTION_ASSIGNED',      'Action Item Assigned'),
        ('ACTION_DUE_SOON',      'Action Item Due Soon (3 days)'),
        ('ACTION_OVERDUE',       'Action Item Overdue'),
        ('ACTION_CLOSED',        'Action Item Closed'),
        ('ESCALATED_TO_HAZARD',  'Action Escalated to Hazard Report'),
    ]

    # Exactly same structure as your IncidentNotification
    recipient           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meeting_notifications')
    meeting             = models.ForeignKey(SafetyMeeting, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    action_item         = models.ForeignKey(MeetingActionItem, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    notification_type   = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title               = models.CharField(max_length=255)
    message             = models.TextField()
    is_read             = models.BooleanField(default=False)
    created_at          = models.DateTimeField(auto_now_add=True)
    read_at             = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Meeting Notification'
        verbose_name_plural = 'Meeting Notifications'

    def __str__(self):
        return f"{self.recipient.get_full_name()} - {self.title}"

    # Exactly like your IncidentNotification.mark_as_read()
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])