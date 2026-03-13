from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.organizations.models import Plant, Zone, Location, SubLocation
from .models import (
    TrainingTopic,
    TrainingRequirement,
    TrainingSession,
    TrainingParticipant,
    TrainingRecord,
)

User = get_user_model()


# ─────────────────────────────────────────────────────────────
# Common widget helpers  (same style as your IncidentReportForm)
# ─────────────────────────────────────────────────────────────

TEXT_INPUT   = {'class': 'form-control'}
SELECT       = {'class': 'form-control'}
TEXTAREA     = {'class': 'form-control', 'rows': 3}
DATE_INPUT   = {'class': 'form-control', 'type': 'date'}
TIME_INPUT   = {'class': 'form-control', 'type': 'time'}
NUMBER_INPUT = {'class': 'form-control'}
FILE_INPUT   = {'class': 'form-control-file'}
CHECKBOX     = {'class': 'form-check-input'}


# ============================================================
# 1. TRAINING TOPIC FORM
#    Like your IncidentTypeForm
# ============================================================

class TrainingTopicForm(forms.ModelForm):

    class Meta:
        model  = TrainingTopic
        fields = [
            'name', 'code', 'category', 'description',
            'validity_period_days', 'passing_score',
            'is_mandatory', 'is_active',
        ]
        widgets = {
            'name':                 forms.TextInput(attrs={**TEXT_INPUT, 'placeholder': 'e.g. Fire Safety Training'}),
            'code':                 forms.TextInput(attrs={**TEXT_INPUT, 'placeholder': 'e.g. FIRE-01', 'style': 'text-transform:uppercase;'}),
            'category':             forms.Select(attrs=SELECT),
            'description':          forms.Textarea(attrs={**TEXTAREA, 'placeholder': 'Describe what this training covers...'}),
            'validity_period_days': forms.NumberInput(attrs={**NUMBER_INPUT, 'min': 1, 'max': 3650}),
            'passing_score':        forms.NumberInput(attrs={**NUMBER_INPUT, 'min': 0, 'max': 100}),
            'is_mandatory':         forms.CheckboxInput(attrs=CHECKBOX),
            'is_active':            forms.CheckboxInput(attrs=CHECKBOX),
        }
        labels = {
            'validity_period_days': 'Validity Period (Days)',
            'passing_score':        'Passing Score (%)',
            'is_mandatory':         'Mandatory Training',
            'is_active':            'Active',
        }

    def clean_code(self):
        # Always store code uppercase
        return self.cleaned_data.get('code', '').strip().upper()

    def clean_passing_score(self):
        score = self.cleaned_data.get('passing_score', 0)
        if score < 0 or score > 100:
            raise forms.ValidationError("Passing score must be between 0 and 100.")
        return score

    def clean_validity_period_days(self):
        days = self.cleaned_data.get('validity_period_days', 365)
        if days < 1:
            raise forms.ValidationError("Validity period must be at least 1 day.")
        return days


# ============================================================
# 2. TRAINING SESSION FORM
#    Like your IncidentReportForm — main create/update form
#    Accepts 'user' kwarg for location filtering (same pattern)
# ============================================================

class TrainingSessionForm(forms.ModelForm):

    class Meta:
        model  = TrainingSession
        fields = [
            # Topic & Mode
            'topic', 'training_mode',
            # Schedule
            'scheduled_date', 'scheduled_time', 'end_time', 'duration_hours',
            # Location
            'plant', 'zone', 'location', 'sublocation', 'venue_details',
            # Trainer
            'trainer_name', 'trainer_designation',
            'trainer_is_external', 'trainer_organization',
            # Session details
            'agenda', 'max_participants', 'remarks', 'attachment',
        ]
        widgets = {
            # Topic & mode
            'topic':               forms.Select(attrs=SELECT),
            'training_mode':       forms.Select(attrs=SELECT),

            # Schedule
            'scheduled_date':      forms.DateInput(attrs=DATE_INPUT),
            'scheduled_time':      forms.TimeInput(attrs=TIME_INPUT),
            'end_time':            forms.TimeInput(attrs=TIME_INPUT),
            'duration_hours':      forms.NumberInput(attrs={**NUMBER_INPUT, 'step': '0.5', 'min': '0.5'}),

            # Location — same as your IncidentReportForm
            'plant':               forms.Select(attrs=SELECT),
            'zone':                forms.Select(attrs=SELECT),
            'location':            forms.Select(attrs=SELECT),
            'sublocation':         forms.Select(attrs=SELECT),
            'venue_details':       forms.TextInput(attrs={**TEXT_INPUT, 'placeholder': 'e.g. Conference Room A, Shop Floor Gate 2'}),

            # Trainer
            'trainer_name':        forms.TextInput(attrs={**TEXT_INPUT, 'placeholder': 'Full name of trainer'}),
            'trainer_designation': forms.TextInput(attrs={**TEXT_INPUT, 'placeholder': 'e.g. Safety Officer, External Consultant'}),
            'trainer_is_external': forms.CheckboxInput(attrs=CHECKBOX),
            'trainer_organization': forms.TextInput(attrs={**TEXT_INPUT, 'placeholder': 'Training organization name (if external)'}),

            # Details
            'agenda':              forms.Textarea(attrs={**TEXTAREA, 'rows': 4, 'placeholder': 'List topics to be covered in this session...'}),
            'max_participants':    forms.NumberInput(attrs={**NUMBER_INPUT, 'min': 1}),
            'remarks':             forms.Textarea(attrs={**TEXTAREA, 'placeholder': 'Any additional notes or special instructions...'}),
            'attachment':          forms.FileInput(attrs=FILE_INPUT),
        }

    def __init__(self, *args, **kwargs):
        # Accept 'user' kwarg exactly like your IncidentReportForm
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # ── Location dropdowns: filter by user's assignments ──
        # Exactly your pattern from IncidentReportForm
        if self.user:
            assigned_plants = self.user.assigned_plants.filter(is_active=True)
            self.fields['plant'].queryset = assigned_plants

            # Zone: filter to user's plant if single plant
            if assigned_plants.count() == 1:
                self.fields['zone'].queryset = self.user.assigned_zones.filter(
                    is_active=True, plant=assigned_plants.first()
                )
            else:
                self.fields['zone'].queryset = Zone.objects.filter(
                    plant__in=assigned_plants, is_active=True
                )

            self.fields['location'].queryset = self.user.assigned_locations.filter(is_active=True)
            self.fields['sublocation'].queryset = self.user.assigned_sublocations.filter(is_active=True)
        else:
            # Superuser / admin: show all active
            self.fields['plant'].queryset     = Plant.objects.filter(is_active=True)
            self.fields['zone'].queryset      = Zone.objects.filter(is_active=True)
            self.fields['location'].queryset  = Location.objects.filter(is_active=True)
            self.fields['sublocation'].queryset = SubLocation.objects.filter(is_active=True)

        # ── Only active topics ──
        self.fields['topic'].queryset = TrainingTopic.objects.filter(is_active=True).order_by('name')

        # ── Empty labels ──
        self.fields['plant'].empty_label        = '-- Select Plant --'
        self.fields['zone'].empty_label         = '-- Select Zone --'
        self.fields['location'].empty_label     = '-- Select Location --'
        self.fields['sublocation'].empty_label  = '-- Select Sub-Location --'
        self.fields['topic'].empty_label        = '-- Select Training Topic --'
        self.fields['training_mode'].empty_label = '-- Select Mode --'

    def clean(self):
        cleaned_data = super().clean()
        scheduled_date = cleaned_data.get('scheduled_date')
        scheduled_time = cleaned_data.get('scheduled_time')
        end_time       = cleaned_data.get('end_time')

        # Scheduled date cannot be in the past (only for new sessions, not edit)
        if not self.instance.pk and scheduled_date:
            if scheduled_date < timezone.now().date():
                self.add_error('scheduled_date', "Scheduled date cannot be in the past.")

        # End time must be after start time
        if scheduled_time and end_time:
            if end_time <= scheduled_time:
                self.add_error('end_time', "End time must be after scheduled start time.")

        # External trainer → organization required
        trainer_is_external  = cleaned_data.get('trainer_is_external')
        trainer_organization = cleaned_data.get('trainer_organization', '').strip()
        if trainer_is_external and not trainer_organization:
            self.add_error('trainer_organization', "Please provide the trainer's organization name for external trainers.")

        return cleaned_data


# ============================================================
# 3. TRAINING SESSION COMPLETE FORM
#    Like your IncidentClosureForm
# ============================================================

class TrainingSessionCompleteForm(forms.ModelForm):

    class Meta:
        model  = TrainingSession
        fields = ['actual_date', 'completion_remarks', 'completion_attachment']
        widgets = {
            'actual_date':          forms.DateInput(attrs=DATE_INPUT),
            'completion_remarks':   forms.Textarea(attrs={**TEXTAREA, 'placeholder': 'Summary notes about the session...'}),
            'completion_attachment': forms.FileInput(attrs=FILE_INPUT),
        }
        labels = {
            'actual_date':          'Actual Conducted Date',
            'completion_remarks':   'Completion Remarks',
            'completion_attachment': 'Attach Proof (attendance sheet / photos)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['actual_date'].required = True
        # Default to today
        if not self.initial.get('actual_date'):
            self.fields['actual_date'].initial = timezone.now().date()

    def clean_actual_date(self):
        actual_date = self.cleaned_data.get('actual_date')
        if actual_date and actual_date > timezone.now().date():
            raise forms.ValidationError("Actual date cannot be in the future.")
        return actual_date


# ============================================================
# 4. TRAINING SESSION CANCEL FORM
# ============================================================

class TrainingSessionCancelForm(forms.ModelForm):

    class Meta:
        model  = TrainingSession
        fields = ['cancelled_reason']
        widgets = {
            'cancelled_reason': forms.Textarea(attrs={
                **TEXTAREA,
                'rows': 4,
                'placeholder': 'Explain why this session is being cancelled...',
                'required': True,
            }),
        }
        labels = {
            'cancelled_reason': 'Reason for Cancellation',
        }

    def clean_cancelled_reason(self):
        reason = self.cleaned_data.get('cancelled_reason', '').strip()
        if not reason:
            raise forms.ValidationError("Please provide a reason for cancellation.")
        if len(reason) < 10:
            raise forms.ValidationError("Please provide a more detailed reason (minimum 10 characters).")
        return reason


# ============================================================
# 5. TRAINING RECORD MANUAL UPLOAD FORM
#    For manually uploading external training certificates
#    Like your IncidentAttachmentForm
# ============================================================

class TrainingRecordManualForm(forms.ModelForm):

    # Extra field for external certificate number (not on model directly)
    external_certificate_number = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={**TEXT_INPUT, 'placeholder': 'Certificate # from external body (optional)'}),
        label='External Certificate Number',
    )

    class Meta:
        model  = TrainingRecord
        fields = [
            'employee', 'topic',
            'completed_date', 'valid_until',
            'certificate_file',
            'status',
        ]
        widgets = {
            'employee':       forms.Select(attrs=SELECT),
            'topic':          forms.Select(attrs=SELECT),
            'completed_date': forms.DateInput(attrs=DATE_INPUT),
            'valid_until':    forms.DateInput(attrs=DATE_INPUT),
            'certificate_file': forms.FileInput(attrs=FILE_INPUT),
            'status':         forms.Select(attrs=SELECT),
        }
        labels = {
            'employee':         'Employee',
            'topic':            'Training Topic',
            'completed_date':   'Training Completion Date',
            'valid_until':      'Certificate Valid Until',
            'certificate_file': 'Attach Certificate (PDF / Image)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Only active employees
        self.fields['employee'].queryset = User.objects.filter(
            is_active=True
        ).order_by('first_name', 'last_name')
        self.fields['employee'].empty_label = '-- Select Employee --'

        # Only active topics
        self.fields['topic'].queryset = TrainingTopic.objects.filter(
            is_active=True
        ).order_by('name')
        self.fields['topic'].empty_label = '-- Select Training Topic --'

        # Default status = ACTIVE
        self.fields['status'].initial = 'ACTIVE'

    def clean(self):
        cleaned_data = super().clean()
        completed_date = cleaned_data.get('completed_date')
        valid_until    = cleaned_data.get('valid_until')

        if completed_date and valid_until:
            if valid_until <= completed_date:
                self.add_error('valid_until', "Valid until date must be after the completion date.")

        if completed_date and completed_date > timezone.now().date():
            self.add_error('completed_date', "Completion date cannot be in the future.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.added_manually = True

        # If external cert number provided, use it as certificate_number override
        ext_cert = self.cleaned_data.get('external_certificate_number', '').strip()
        if ext_cert:
            instance.certificate_number = ext_cert

        if commit:
            instance.save()
        return instance


# ============================================================
# 6. TRAINING PARTICIPANT FORMSET
#    Used when bulk-managing participants in a session
#    Like your ActionItemFormSet pattern
# ============================================================

class TrainingParticipantForm(forms.ModelForm):

    class Meta:
        model  = TrainingParticipant
        fields = ['employee', 'attendance_status', 'assessment_score', 'remarks']
        widgets = {
            'employee':          forms.Select(attrs=SELECT),
            'attendance_status': forms.Select(attrs=SELECT),
            'assessment_score':  forms.NumberInput(attrs={**NUMBER_INPUT, 'min': 0, 'max': 100, 'placeholder': '0-100'}),
            'remarks':           forms.TextInput(attrs={**TEXT_INPUT, 'placeholder': 'Optional remarks'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = User.objects.filter(
            is_active=True
        ).order_by('first_name', 'last_name')


# ============================================================
# 7. TRAINING REQUIREMENT FORM
#    For configuring who needs which training
# ============================================================

class TrainingRequirementForm(forms.ModelForm):

    class Meta:
        model  = TrainingRequirement
        fields = [
            'topic', 'applicable_to',
            'role', 'department', 'plant',
            'due_within_days',
        ]
        widgets = {
            'topic':          forms.Select(attrs=SELECT),
            'applicable_to':  forms.Select(attrs=SELECT),
            'role':           forms.Select(attrs=SELECT),
            'department':     forms.Select(attrs=SELECT),
            'plant':          forms.Select(attrs=SELECT),
            'due_within_days': forms.NumberInput(attrs={**NUMBER_INPUT, 'min': 1}),
        }
        labels = {
            'applicable_to':   'Applicable To',
            'due_within_days': 'Must Complete Within (Days)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['topic'].queryset = TrainingTopic.objects.filter(
            is_active=True
        ).order_by('name')
        self.fields['topic'].empty_label       = '-- Select Topic --'
        self.fields['applicable_to'].empty_label = '-- Select Scope --'
        self.fields['role'].empty_label        = '-- Select Role (if applicable) --'
        self.fields['department'].empty_label  = '-- Select Department (if applicable) --'
        self.fields['plant'].empty_label       = '-- Select Plant (if applicable) --'

        # role, department, plant are optional by default
        self.fields['role'].required       = False
        self.fields['department'].required = False
        self.fields['plant'].required      = False

    def clean(self):
        cleaned_data  = super().clean()
        applicable_to = cleaned_data.get('applicable_to')
        role          = cleaned_data.get('role')
        department    = cleaned_data.get('department')
        plant         = cleaned_data.get('plant')

        # Validate that the linked FK is set when required
        if applicable_to == 'ROLE' and not role:
            self.add_error('role', "Please select a role when scope is 'Specific Role'.")

        if applicable_to == 'DEPARTMENT' and not department:
            self.add_error('department', "Please select a department when scope is 'Specific Department'.")

        if applicable_to == 'PLANT' and not plant:
            self.add_error('plant', "Please select a plant when scope is 'Specific Plant'.")

        return cleaned_data


# ============================================================
# 8. FORMSET — Training Participants
#    Used in MarkAttendanceView
# ============================================================

from django.forms import inlineformset_factory

TrainingParticipantFormSet = inlineformset_factory(
    TrainingSession,
    TrainingParticipant,
    form=TrainingParticipantForm,
    fields=['employee', 'attendance_status', 'assessment_score', 'remarks'],
    extra=0,
    can_delete=False,
)