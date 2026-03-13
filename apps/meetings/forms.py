from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth import get_user_model
from apps.organizations.models import Plant, Zone, Location, SubLocation
from .models import SafetyMeeting, MeetingAttendee, MeetingActionItem

User = get_user_model()


# ============================================================
# 1. SAFETY MEETING FORM (Create / Edit)
# ============================================================

class SafetyMeetingForm(forms.ModelForm):

    class Meta:
        model = SafetyMeeting
        fields = [
            'title', 'meeting_type',
            'plant', 'zone', 'location', 'sublocation', 'venue_details',
            'scheduled_date', 'scheduled_time', 'end_time',
            'chairperson',
            'agenda', 'agenda_attachment',
        ]
        widgets = {
            'title':             forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Monthly Safety Review - April 2025'}),
            'meeting_type':      forms.Select(attrs={'class': 'form-control'}),
            'plant':             forms.Select(attrs={'class': 'form-control', 'id': 'id_plant'}),
            'zone':              forms.Select(attrs={'class': 'form-control', 'id': 'id_zone'}),
            'location':          forms.Select(attrs={'class': 'form-control', 'id': 'id_location'}),
            'sublocation':       forms.Select(attrs={'class': 'form-control', 'id': 'id_sublocation'}),
            'venue_details':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Conference Room A'}),
            'scheduled_date':    forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'scheduled_time':    forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time':          forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'chairperson':       forms.Select(attrs={'class': 'form-control'}),
            'agenda':            forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'List agenda items...'}),
            'agenda_attachment': forms.FileInput(attrs={'class': 'form-control-file'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Empty labels
        self.fields['plant'].empty_label       = 'Select Plant'
        self.fields['zone'].empty_label        = 'Select Zone'
        self.fields['location'].empty_label    = 'Select Location'
        self.fields['sublocation'].empty_label = 'Select Sub-Location (Optional)'
        self.fields['chairperson'].empty_label = 'Select Chairperson'

        # Optional fields
        self.fields['zone'].required             = False
        self.fields['sublocation'].required      = False
        self.fields['end_time'].required         = False
        self.fields['agenda_attachment'].required = False

        # ── Plant dropdown ──
        # get_all_plants() returns a list — convert to QuerySet via id__in
        if self.user and not self.user.is_superuser:
            plant_ids = [p.id for p in self.user.get_all_plants()]
            self.fields['plant'].queryset = Plant.objects.filter(id__in=plant_ids)

            self.fields['chairperson'].queryset = User.objects.filter(
                is_active=True,
                assigned_plants__in=plant_ids
            ).distinct().order_by('first_name', 'last_name')
        else:
            # Superuser sees all
            self.fields['plant'].queryset = Plant.objects.filter(is_active=True)
            self.fields['chairperson'].queryset = User.objects.filter(
                is_active=True
            ).order_by('first_name', 'last_name')

        # ── Zone / Location / SubLocation ──
        # Resolve plant_id from: (1) existing instance, (2) POST data, (3) none
        plant_id = None
        if self.instance and self.instance.pk and self.instance.plant_id:
            plant_id = self.instance.plant_id
        elif self.data.get('plant'):
            # POST submission — plant selected by user via AJAX chain
            try:
                plant_id = int(self.data.get('plant'))
            except (ValueError, TypeError):
                plant_id = None

        if plant_id:
            self.fields['zone'].queryset = Zone.objects.filter(
                plant_id=plant_id
            )
            self.fields['location'].queryset = Location.objects.filter(
                zone__plant_id=plant_id
            )
            self.fields['sublocation'].queryset = SubLocation.objects.filter(
                location__zone__plant_id=plant_id
            )
        else:
            # No plant selected yet — empty, filled via AJAX
            self.fields['zone'].queryset        = Zone.objects.none()
            self.fields['location'].queryset    = Location.objects.none()
            self.fields['sublocation'].queryset = SubLocation.objects.none()


# ============================================================
# 2. COMPLETE MEETING FORM
# ============================================================

class SafetyMeetingCompleteForm(forms.ModelForm):

    class Meta:
        model = SafetyMeeting
        fields = [
            'actual_date', 'actual_start_time', 'actual_end_time',
            'minutes_of_meeting', 'mom_attachment',
        ]
        widgets = {
            'actual_date':        forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'actual_start_time':  forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'actual_end_time':    forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'minutes_of_meeting': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 8,
                'placeholder': 'Record full minutes of the meeting — discussion points, decisions taken, follow-ups agreed...'
            }),
            'mom_attachment': forms.FileInput(attrs={'class': 'form-control-file'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['actual_start_time'].required = False
        self.fields['actual_end_time'].required   = False
        self.fields['mom_attachment'].required    = False

    def clean(self):
        cleaned_data = super().clean()
        minutes = cleaned_data.get('minutes_of_meeting', '')
        if len(minutes.strip()) < 20:
            raise forms.ValidationError(
                "Minutes of Meeting must be at least 20 characters. Please record what was discussed."
            )
        return cleaned_data


# ============================================================
# 3. CANCEL MEETING FORM
# ============================================================

class SafetyMeetingCancelForm(forms.ModelForm):

    class Meta:
        model = SafetyMeeting
        fields = ['cancelled_reason']
        widgets = {
            'cancelled_reason': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Provide reason for cancellation (minimum 10 characters)...'
            }),
        }

    def clean_cancelled_reason(self):
        reason = self.cleaned_data.get('cancelled_reason', '').strip()
        if len(reason) < 10:
            raise forms.ValidationError("Please provide a proper reason (at least 10 characters).")
        return reason


# ============================================================
# 4. MEETING ACTION ITEM FORM
# ============================================================

class MeetingActionItemForm(forms.ModelForm):

    class Meta:
        model = MeetingActionItem
        fields = ['description', 'priority', 'assigned_to', 'due_date']
        widgets = {
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe the action to be taken...'}),
            'priority':    forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'due_date':    forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.meeting = kwargs.pop('meeting', None)
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].empty_label = 'Select Responsible Person'

        # Use plant_id (int) to avoid list/queryset confusion
        if self.meeting and self.meeting.plant_id:
            self.fields['assigned_to'].queryset = User.objects.filter(
                is_active=True,
                assigned_plants=self.meeting.plant_id
            ).distinct().order_by('first_name', 'last_name')
        else:
            self.fields['assigned_to'].queryset = User.objects.filter(
                is_active=True
            ).order_by('first_name', 'last_name')


# ============================================================
# 5. ACTION ITEM CLOSURE FORM
# ============================================================

class ActionItemCloseForm(forms.ModelForm):

    class Meta:
        model = MeetingActionItem
        fields = ['closure_remarks', 'closure_attachment']
        widgets = {
            'closure_remarks':    forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe what was done to close this action item...'}),
            'closure_attachment': forms.FileInput(attrs={'class': 'form-control-file'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['closure_attachment'].required = False

    def clean_closure_remarks(self):
        remarks = self.cleaned_data.get('closure_remarks', '').strip()
        if len(remarks) < 10:
            raise forms.ValidationError("Please provide proper closure remarks (at least 10 characters).")
        return remarks


# ============================================================
# 6. ADD ATTENDEES FORM
# ============================================================

class AddAttendeesForm(forms.Form):
    employees = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple(),
        label="Select Employees to Invite"
    )

    def __init__(self, *args, **kwargs):
        meeting = kwargs.pop('meeting', None)
        super().__init__(*args, **kwargs)

        qs = User.objects.filter(is_active=True)

        # Use plant_id (int) — not plant object
        if meeting and meeting.plant_id:
            qs = qs.filter(assigned_plants=meeting.plant_id)

        # Exclude already added attendees
        if meeting:
            already_added = meeting.attendees.values_list('employee_id', flat=True)
            qs = qs.exclude(id__in=already_added)

        self.fields['employees'].queryset = qs.distinct().order_by('first_name', 'last_name')


# ============================================================
# 7. MARK ATTENDANCE FORMSET
# ============================================================

MeetingAttendeeFormSet = inlineformset_factory(
    SafetyMeeting,
    MeetingAttendee,
    fields=['attendance_status', 'signed', 'remarks'],
    widgets={
        'attendance_status': forms.Select(attrs={'class': 'form-control form-control-sm'}),
        'signed':            forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        'remarks':           forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Optional remarks'}),
    },
    extra=0,
    can_delete=False,
)