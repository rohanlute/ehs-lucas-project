import datetime
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.organizations.models import Plant, Zone, Location, SubLocation, Department
from apps.accounts.models import Role

User = get_user_model()


# ============================================================
# 1. TRAINING TOPIC (Master Table — like your IncidentType)
# ============================================================

class TrainingTopic(models.Model):
    
    CATEGORY_CHOICES = [
        ('INDUCTION',          'Induction Training'),
        ('REFRESHER',          'Refresher Training'),
        ('TOOLBOX_TALK',       'Toolbox Talk'),
        ('FIRE_SAFETY',        'Fire Safety'),
        ('PPE',                'PPE Usage'),
        ('EMERGENCY_RESPONSE', 'Emergency Response'),
        ('HAZARD_AWARENESS',   'Hazard Awareness'),
        ('FIRST_AID',          'First Aid'),
        ('ENVIRONMENTAL',      'Environmental'),
        ('CHEMICAL_HANDLING',  'Chemical Handling'),
        ('MACHINE_SAFETY',     'Machine Safety'),
        ('WORK_AT_HEIGHT',     'Work at Height'),
        ('ELECTRICAL_SAFETY',  'Electrical Safety'),
        ('CUSTOM',             'Custom / Other'),
    ]

    name                = models.CharField(max_length=200, unique=True)
    code                = models.CharField(max_length=20, unique=True, help_text="Short code e.g. FIRE-01")
    description         = models.TextField(blank=True)
    category            = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='CUSTOM')
    validity_period_days= models.PositiveIntegerField(
                            default=365,
                            help_text="After this many days, employee's certificate expires and they become non-compliant"
                          )
    passing_score       = models.PositiveIntegerField(
                            default=70,
                            help_text="Minimum score (%) required to pass assessment. Set 0 if no assessment."
                          )
    is_mandatory        = models.BooleanField(default=False, help_text="If True, all applicable employees must complete this")
    is_active           = models.BooleanField(default=True)
    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='training_topics_created')
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Training Topic'
        verbose_name_plural = 'Training Topics'

    def __str__(self):
        return f"{self.name} ({self.code})"


# ============================================================
# 2. TRAINING REQUIREMENT
#    Defines which role/dept/plant needs which training
#    Matches your User model fields: role, department, plant
# ============================================================

class TrainingRequirement(models.Model):

    APPLICABLE_TO_CHOICES = [
        ('ALL',        'All Employees'),
        ('ROLE',       'Specific Role'),
        ('DEPARTMENT', 'Specific Department'),
        ('PLANT',      'Specific Plant'),
    ]

    topic           = models.ForeignKey(TrainingTopic, on_delete=models.CASCADE, related_name='requirements')
    applicable_to   = models.CharField(max_length=20, choices=APPLICABLE_TO_CHOICES, default='ALL')

    # These match exactly your User model FK fields
    role            = models.ForeignKey(Role, on_delete=models.CASCADE, null=True, blank=True, related_name='training_requirements')
    department      = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True, related_name='training_requirements')
    plant           = models.ForeignKey(Plant, on_delete=models.CASCADE, null=True, blank=True, related_name='training_requirements')

    due_within_days = models.PositiveIntegerField(
                        default=30,
                        help_text="New employee must complete this training within these many days of joining"
                      )
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='training_requirements_created')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Training Requirement'
        verbose_name_plural = 'Training Requirements'

    def __str__(self):
        return f"{self.topic.name} → {self.get_applicable_to_display()}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.applicable_to == 'ROLE' and not self.role:
            raise ValidationError("Role is required when applicable_to is 'Specific Role'")
        if self.applicable_to == 'DEPARTMENT' and not self.department:
            raise ValidationError("Department is required when applicable_to is 'Specific Department'")
        if self.applicable_to == 'PLANT' and not self.plant:
            raise ValidationError("Plant is required when applicable_to is 'Specific Plant'")


# ============================================================
# 3. TRAINING SESSION (Main model — like your Incident model)
# ============================================================

class TrainingSession(models.Model):

    STATUS_CHOICES = [
        ('SCHEDULED',  'Scheduled'),
        ('ONGOING',    'Ongoing'),
        ('COMPLETED',  'Completed'),
        ('CANCELLED',  'Cancelled'),
    ]

    TRAINING_MODE_CHOICES = [
        ('CLASSROOM',    'Classroom Training'),
        ('TOOLBOX_TALK', 'Toolbox Talk'),
        ('OJT',          'On-the-Job Training (OJT)'),
        ('ONLINE',       'Online / e-Learning'),
        ('MOCK_DRILL',   'Mock Drill'),
        ('SEMINAR',      'Seminar / Workshop'),
    ]

    # Auto-generated: TRN-{PLANT_CODE}-{YYYYMMDD}-{001}
    # Exactly like your report_number on Incident
    session_number  = models.CharField(max_length=50, unique=True, editable=False)

    topic           = models.ForeignKey(TrainingTopic, on_delete=models.CASCADE, related_name='sessions')
    training_mode   = models.CharField(max_length=20, choices=TRAINING_MODE_CHOICES, default='CLASSROOM')

    # ── Same location chain as your Incident model ──
    plant           = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name='training_sessions')
    zone            = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='training_sessions')
    location        = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='training_sessions')
    sublocation     = models.ForeignKey(SubLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='training_sessions')
    venue_details   = models.CharField(max_length=255, blank=True, help_text="e.g. Conference Room A, Shop Floor Gate 2")

    # ── Schedule ──
    scheduled_date  = models.DateField()
    scheduled_time  = models.TimeField()
    end_time        = models.TimeField(null=True, blank=True)
    duration_hours  = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    # ── Trainer Info ──
    trainer_name            = models.CharField(max_length=200)
    trainer_designation     = models.CharField(max_length=100, blank=True)
    trainer_is_external     = models.BooleanField(default=False, help_text="Is trainer from outside the organization?")
    trainer_organization    = models.CharField(max_length=200, blank=True, help_text="If external trainer, their organization name")

    # ── Session Details ──
    agenda          = models.TextField(blank=True, help_text="Topics/agenda to be covered in this session")
    max_participants= models.PositiveIntegerField(default=30)
    remarks         = models.TextField(blank=True)
    attachment      = models.FileField(
                        upload_to='training_materials/%Y/%m/',
                        null=True, blank=True,
                        help_text="Upload training material, presentation, PDF etc."
                      )

    # ── Workflow Status (like your Incident.STATUS_CHOICES) ──
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    cancelled_reason= models.TextField(blank=True, help_text="Reason if session is cancelled")

    # ── Completion Info (filled when status → COMPLETED) ──
    actual_date             = models.DateField(null=True, blank=True, help_text="Actual date session was conducted")
    completion_remarks      = models.TextField(blank=True)
    completion_attachment   = models.FileField(
                                upload_to='training_completion/%Y/%m/',
                                null=True, blank=True,
                                help_text="Upload attendance sheet, photos, or any proof of completion"
                              )

    # ── Same created_by pattern as your other models ──
    created_by      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_sessions_created')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date', '-scheduled_time']
        verbose_name = 'Training Session'
        verbose_name_plural = 'Training Sessions'

    def __str__(self):
        return f"{self.session_number} - {self.topic.name}"

    def save(self, *args, **kwargs):
        # Auto-generate session_number like your report_number logic
        if not self.session_number:
            today = datetime.date.today()
            date_str = today.strftime('%Y%m%d')
            plant_code = self.plant.code if self.plant else 'XXX'

            count = TrainingSession.objects.filter(
                session_number__contains=f'TRN-{plant_code}-{date_str}'
            ).count()

            self.session_number = f'TRN-{plant_code}-{date_str}-{count + 1:03d}'

        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        """Session was scheduled but not completed past its date"""
        if self.status == 'SCHEDULED' and self.scheduled_date:
            return datetime.date.today() > self.scheduled_date
        return False

    @property
    def total_invited(self):
        return self.participants.count()

    @property
    def total_present(self):
        return self.participants.filter(attendance_status='PRESENT').count()

    @property
    def attendance_percentage(self):
        if self.total_invited == 0:
            return 0
        return round((self.total_present / self.total_invited) * 100, 1)

    @property
    def can_be_completed(self):
        """Check if session can be marked as completed"""
        if self.status == 'COMPLETED':
            return False, "Session is already completed"
        if self.status == 'CANCELLED':
            return False, "Cancelled session cannot be completed"
        if self.participants.count() == 0:
            return False, "No participants added to this session"
        return True, "Ready to complete"


# ============================================================
# 4. TRAINING PARTICIPANT
#    Like your IncidentActionItem — per employee per session
# ============================================================

class TrainingParticipant(models.Model):

    ATTENDANCE_STATUS_CHOICES = [
        ('INVITED',  'Invited'),   # default when added
        ('PRESENT',  'Present'),
        ('ABSENT',   'Absent'),
        ('PARTIAL',  'Partial Attendance'),
    ]

    session             = models.ForeignKey(TrainingSession, on_delete=models.CASCADE, related_name='participants')

    # FK to your User model
    employee            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_participations')

    attendance_status   = models.CharField(max_length=10, choices=ATTENDANCE_STATUS_CHOICES, default='INVITED')

    # Assessment (optional — set passing_score=0 on topic to skip)
    assessment_score    = models.PositiveIntegerField(
                            null=True, blank=True,
                            help_text="Score out of 100. Leave blank if no assessment."
                          )
    passed              = models.BooleanField(
                            null=True, blank=True,
                            help_text="Auto-set based on score vs topic's passing_score"
                          )

    remarks             = models.TextField(blank=True)

    # Who marked the attendance
    marked_by           = models.ForeignKey(
                            User, on_delete=models.SET_NULL,
                            null=True, blank=True,
                            related_name='training_attendance_marked'
                          )
    marked_at           = models.DateTimeField(null=True, blank=True)

    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['employee__first_name']
        # One employee can only be in a session once
        unique_together = ('session', 'employee')
        verbose_name = 'Training Participant'
        verbose_name_plural = 'Training Participants'

    def __str__(self):
        return f"{self.session.session_number} - {self.employee.get_full_name()}"

    def save(self, *args, **kwargs):
        # Auto-calculate passed based on score vs topic's passing_score
        if self.assessment_score is not None:
            passing = self.session.topic.passing_score
            if passing == 0:
                # No assessment required — present = passed
                self.passed = (self.attendance_status == 'PRESENT')
            else:
                self.passed = self.assessment_score >= passing
        elif self.attendance_status == 'PRESENT' and self.session.topic.passing_score == 0:
            # No assessment topic — attendance = pass
            self.passed = True
        super().save(*args, **kwargs)


# ============================================================
# 5. TRAINING RECORD (Permanent certificate record)
#    Created automatically when session is completed
#    OR manually uploaded for external trainings
# ============================================================

class TrainingRecord(models.Model):

    STATUS_CHOICES = [
        ('ACTIVE',   'Active'),
        ('EXPIRED',  'Expired'),
        ('REVOKED',  'Revoked'),
    ]

    employee            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_records')
    topic               = models.ForeignKey(TrainingTopic, on_delete=models.CASCADE, related_name='training_records')

    # Nullable because manually uploaded records won't have a session
    session             = models.ForeignKey(
                            TrainingSession, on_delete=models.SET_NULL,
                            null=True, blank=True,
                            related_name='training_records'
                          )

    completed_date      = models.DateField()
    valid_until         = models.DateField(
                            help_text="Auto-calculated: completed_date + topic's validity_period_days"
                          )

    # Auto-generated: CERT-{EMP_ID}-{TOPIC_CODE}-{YEAR}
    certificate_number  = models.CharField(max_length=100, unique=True, editable=False)
    certificate_file    = models.FileField(
                            upload_to='training_certificates/%Y/%m/',
                            null=True, blank=True
                          )

    status              = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')

    # True if this record was added manually (external training)
    # False if auto-created from session completion
    added_manually      = models.BooleanField(
                            default=False,
                            help_text="True = uploaded manually for external training. False = auto-created from system session."
                          )

    revoked_reason      = models.TextField(blank=True)
    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='training_records_created')
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-completed_date']
        verbose_name = 'Training Record'
        verbose_name_plural = 'Training Records'

    def __str__(self):
        return f"{self.certificate_number} - {self.employee.get_full_name()} - {self.topic.name}"

    def save(self, *args, **kwargs):
        # Auto-calculate valid_until
        if not self.valid_until and self.completed_date:
            self.valid_until = self.completed_date + datetime.timedelta(
                days=self.topic.validity_period_days
            )

        # Auto-generate certificate_number: CERT-{EMP_ID}-{TOPIC_CODE}-{YEAR}
        if not self.certificate_number:
            emp_id = self.employee.employee_id or str(self.employee.id)
            topic_code = self.topic.code
            year = self.completed_date.year if self.completed_date else datetime.date.today().year

            # Handle duplicates in same year
            base = f'CERT-{emp_id}-{topic_code}-{year}'
            count = TrainingRecord.objects.filter(
                certificate_number__startswith=base
            ).count()
            if count == 0:
                self.certificate_number = base
            else:
                self.certificate_number = f'{base}-{count + 1:02d}'

        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return self.valid_until < datetime.date.today()

    @property
    def days_until_expiry(self):
        delta = self.valid_until - datetime.date.today()
        return delta.days

    @property
    def expiry_status(self):
        days = self.days_until_expiry
        if days < 0:
            return 'EXPIRED'
        elif days <= 7:
            return 'EXPIRING_CRITICAL'   # Red
        elif days <= 30:
            return 'EXPIRING_SOON'       # Orange
        elif days <= 60:
            return 'EXPIRING_WARNING'    # Yellow
        else:
            return 'ACTIVE'              # Green


# ============================================================
# 6. TRAINING NOTIFICATION
# ============================================================

class TrainingNotification(models.Model):

    NOTIFICATION_TYPES = [
        ('SESSION_SCHEDULED',    'Training Session Scheduled'),
        ('SESSION_REMINDER',     'Session Reminder (1 day before)'),
        ('SESSION_CANCELLED',    'Session Cancelled'),
        ('ATTENDANCE_MARKED',    'Attendance Marked'),
        ('CERTIFICATE_ISSUED',   'Certificate Issued'),
        ('EXPIRY_ALERT_60',      'Certificate Expiring in 60 Days'),
        ('EXPIRY_ALERT_30',      'Certificate Expiring in 30 Days'),
        ('EXPIRY_ALERT_7',       'Certificate Expiring in 7 Days'),
        ('CERTIFICATE_EXPIRED',  'Certificate Expired'),
        ('TRAINING_OVERDUE',     'Mandatory Training Overdue'),
    ]

    # Exactly same structure as your IncidentNotification
    recipient           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_notifications')
    session             = models.ForeignKey(TrainingSession, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    training_record     = models.ForeignKey(TrainingRecord, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
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
        verbose_name = 'Training Notification'
        verbose_name_plural = 'Training Notifications'

    def __str__(self):
        return f"{self.recipient.get_full_name()} - {self.title}"

    # Exactly like your IncidentNotification.mark_as_read()
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])