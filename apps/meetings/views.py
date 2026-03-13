import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q, Count

from .models import SafetyMeeting, MeetingAttendee, MeetingActionItem, MeetingNotification
from .forms import (
    SafetyMeetingForm, SafetyMeetingCompleteForm, SafetyMeetingCancelForm,
    MeetingActionItemForm, ActionItemCloseForm,
    AddAttendeesForm, MeetingAttendeeFormSet,
)


# ============================================================
# HELPER — Permission mixin
# Same pattern as your TrainingAccessMixin / HazardAccessMixin
# ============================================================

def meeting_access_required(view_func):
    """Decorator: user must have can_access_meeting_module"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not (request.user.can_access_meeting_module or request.user.is_superuser):
            messages.error(request, "You don't have permission to access the Safety Meeting module.")
            return redirect('dashboard:home')
        return view_func(request, *args, **kwargs)
    return wrapper


def _send_notification(recipient, meeting=None, action_item=None,
                        notification_type='', title='', message=''):
    """Helper to create a MeetingNotification — same pattern as your other modules"""
    MeetingNotification.objects.create(
        recipient=recipient,
        meeting=meeting,
        action_item=action_item,
        notification_type=notification_type,
        title=title,
        message=message,
    )


# ============================================================
# 1. DASHBOARD
# ============================================================

# ============================================================
# REPLACE the existing meeting_dashboard view in meeting_views.py
# ============================================================

@login_required
@meeting_access_required
def meeting_dashboard(request):
    import json
    from django.db.models import Avg, FloatField
    from django.db.models.functions import TruncMonth

    user        = request.user
    user_plants = user.get_all_plants()
    plant_ids   = [p.id for p in user_plants]

    base_qs    = SafetyMeeting.objects.filter(plant__in=plant_ids)
    action_qs  = MeetingActionItem.objects.filter(meeting__plant__in=plant_ids)
    today      = datetime.date.today()

    # ── Stat Cards ──
    total     = base_qs.count()
    scheduled = base_qs.filter(status='SCHEDULED').count()
    completed = base_qs.filter(status='COMPLETED').count()
    cancelled = base_qs.filter(status='CANCELLED').count()
    in_prog   = base_qs.filter(status='IN_PROGRESS').count()
    overdue_meetings = [m for m in base_qs.filter(status='SCHEDULED') if m.is_overdue]

    # Action item stats
    total_actions   = action_qs.count()
    open_actions    = action_qs.filter(status='OPEN').count()
    closed_actions  = action_qs.filter(status='CLOSED').count()
    overdue_actions = [a for a in action_qs.filter(status__in=['OPEN', 'IN_PROGRESS']) if a.is_overdue]

    # ── Upcoming (next 30 days) ──
    upcoming = base_qs.filter(
        status='SCHEDULED',
        scheduled_date__gte=today,
        scheduled_date__lte=today + datetime.timedelta(days=30)
    ).select_related('plant', 'location', 'chairperson').order_by('scheduled_date')[:5]

    # ── Recent Completed ──
    recent_completed = base_qs.filter(
        status='COMPLETED'
    ).select_related('plant', 'location').order_by('-updated_at')[:5]

    # ── My open action items ──
    my_action_items = MeetingActionItem.objects.filter(
        assigned_to=user,
        status__in=['OPEN', 'IN_PROGRESS']
    ).select_related('meeting').order_by('due_date')[:10]

    # ── Unread notifications ──
    unread_count = MeetingNotification.objects.filter(
        recipient=user, is_read=False
    ).count()

    # ══════════════════════════════════════════
    # CHART DATA
    # ══════════════════════════════════════════

    # 1. Meetings by Type (Doughnut)
    type_data = (
        base_qs
        .values('meeting_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    type_labels  = [d['meeting_type'].replace('_', ' ').title() for d in type_data]
    type_counts  = [d['count'] for d in type_data]

    # 2. Meetings by Status (Bar)
    status_counts = {
        'Scheduled':   scheduled,
        'In Progress': in_prog,
        'Completed':   completed,
        'Cancelled':   cancelled,
    }

    # 3. Monthly Meeting Trend — last 6 months (Line)
    six_months_ago = today.replace(day=1) - datetime.timedelta(days=150)
    monthly_data = (
        base_qs
        .filter(scheduled_date__gte=six_months_ago)
        .annotate(month=TruncMonth('scheduled_date'))
        .values('month')
        .annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='COMPLETED')),
        )
        .order_by('month')
    )
    monthly_labels    = [d['month'].strftime('%b %Y') for d in monthly_data]
    monthly_totals    = [d['total'] for d in monthly_data]
    monthly_completed = [d['completed'] for d in monthly_data]

    # 4. Action Items by Priority (Doughnut)
    priority_data = (
        action_qs
        .filter(status__in=['OPEN', 'IN_PROGRESS'])
        .values('priority')
        .annotate(count=Count('id'))
        .order_by('priority')
    )
    priority_labels = [d['priority'] for d in priority_data]
    priority_counts = [d['count'] for d in priority_data]

    # 5. Meetings by Plant (Horizontal Bar) — only if multi-plant user
    plant_data = (
        base_qs
        .values('plant__name')
        .annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='COMPLETED')),
        )
        .order_by('-total')[:8]
    )
    plant_labels    = [d['plant__name'] for d in plant_data]
    plant_totals    = [d['total'] for d in plant_data]
    plant_completed = [d['completed'] for d in plant_data]

    # 6. Action Closure Rate — this month vs last month
    this_month_start = today.replace(day=1)
    last_month_start = (this_month_start - datetime.timedelta(days=1)).replace(day=1)

    this_month_actions = action_qs.filter(created_at__date__gte=this_month_start)
    last_month_actions = action_qs.filter(
        created_at__date__gte=last_month_start,
        created_at__date__lt=this_month_start
    )

    def closure_rate(qs):
        t = qs.count()
        c = qs.filter(status='CLOSED').count()
        return round((c / t * 100), 1) if t > 0 else 0

    this_month_rate = closure_rate(this_month_actions)
    last_month_rate = closure_rate(last_month_actions)

    # 7. Attendance Rate — last 10 completed meetings
    last_10 = base_qs.filter(status='COMPLETED').order_by('-actual_date')[:10]
    attendance_labels = [m.meeting_number for m in last_10]
    attendance_rates  = [m.attendance_percentage for m in last_10]

    context = {
        # Stats
        'total': total,
        'scheduled': scheduled,
        'completed': completed,
        'cancelled': cancelled,
        'in_progress': in_prog,
        'overdue_count': len(overdue_meetings),
        'overdue_meetings': overdue_meetings[:5],
        'total_actions': total_actions,
        'open_actions': open_actions,
        'closed_actions': closed_actions,
        'overdue_actions_count': len(overdue_actions),
        'this_month_rate': this_month_rate,
        'last_month_rate': last_month_rate,

        # Lists
        'upcoming': upcoming,
        'recent_completed': recent_completed,
        'my_action_items': my_action_items,
        'unread_count': unread_count,

        # Chart data — serialized to JSON for JS
        'type_labels':        json.dumps(type_labels),
        'type_counts':        json.dumps(type_counts),

        'status_labels':      json.dumps(list(status_counts.keys())),
        'status_counts':      json.dumps(list(status_counts.values())),

        'monthly_labels':     json.dumps(monthly_labels),
        'monthly_totals':     json.dumps(monthly_totals),
        'monthly_completed':  json.dumps(monthly_completed),

        'priority_labels':    json.dumps(priority_labels),
        'priority_counts':    json.dumps(priority_counts),

        'plant_labels':       json.dumps(plant_labels),
        'plant_totals':       json.dumps(plant_totals),
        'plant_completed':    json.dumps(plant_completed),

        'attendance_labels':  json.dumps(attendance_labels),
        'attendance_rates':   json.dumps(attendance_rates),

        'page_title': 'Safety Meeting Dashboard',
    }
    return render(request, 'meetings/dashboard.html', context)


# ============================================================
# 2. MEETING LIST
# ============================================================

@login_required
@meeting_access_required
def meeting_list(request):
    user = request.user
    user_plants = user.get_all_plants()
    meetings = SafetyMeeting.objects.filter(plant__in=user_plants)

    # Filters
    status      = request.GET.get('status', '')
    mtype       = request.GET.get('type', '')
    plant_id    = request.GET.get('plant', '')
    search      = request.GET.get('search', '')
    date_from   = request.GET.get('date_from', '')
    date_to     = request.GET.get('date_to', '')

    if status:
        meetings = meetings.filter(status=status)
    if mtype:
        meetings = meetings.filter(meeting_type=mtype)
    if plant_id:
        meetings = meetings.filter(plant_id=plant_id)
    if search:
        meetings = meetings.filter(
            Q(meeting_number__icontains=search) |
            Q(title__icontains=search) |
            Q(chairperson__first_name__icontains=search) |
            Q(chairperson__last_name__icontains=search)
        )
    if date_from:
        meetings = meetings.filter(scheduled_date__gte=date_from)
    if date_to:
        meetings = meetings.filter(scheduled_date__lte=date_to)

    meetings = meetings.select_related('plant', 'location', 'chairperson', 'created_by')

    context = {
        'meetings': meetings,
        'status_choices': SafetyMeeting.STATUS_CHOICES,
        'type_choices': SafetyMeeting.MEETING_TYPE_CHOICES,
        'user_plants': user_plants,
        'selected_status': status,
        'selected_type': mtype,
        'selected_plant': plant_id,
        'search': search,
        'page_title': 'Safety Meetings',
    }
    return render(request, 'meetings/meeting_list.html', context)


# ============================================================
# 3. MEETING CREATE
# ============================================================

@login_required
@meeting_access_required
def meeting_create(request):
    user = request.user

    if not (user.can_create_meeting or user.is_superuser):
        messages.error(request, "You don't have permission to create a Safety Meeting.")
        return redirect('meetings:meeting_list')

    if request.method == 'POST':
        form = SafetyMeetingForm(request.POST, request.FILES, user=user)
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.created_by = user
            meeting.status = 'SCHEDULED'
            meeting.save()
            messages.success(request, f"Meeting {meeting.meeting_number} created successfully.")
            return redirect('meetings:meeting_detail', pk=meeting.pk)
    else:
        form = SafetyMeetingForm(user=user)

    user_plants = user.get_all_plants()
    context = {
        'form': form,
        'user_plants': user_plants,
        'user_assigned_plants': user_plants,
        'page_title': 'Schedule Safety Meeting',
    }
    return render(request, 'meetings/meeting_create.html', context)


# ============================================================
# 4. MEETING DETAIL
# ============================================================

@login_required
@meeting_access_required
def meeting_detail(request, pk):
    user = request.user
    user_plants = user.get_all_plants()

    meeting = get_object_or_404(
        SafetyMeeting.objects.select_related(
            'plant', 'zone', 'location', 'sublocation',
            'chairperson', 'created_by'
        ),
        pk=pk,
        plant__in=user_plants
    )

    attendees     = meeting.attendees.select_related('employee', 'marked_by')
    action_items  = meeting.action_items.select_related('assigned_to', 'assigned_by', 'closed_by', 'hazard_report')
    notifications = meeting.notifications.filter(recipient=user).order_by('-created_at')[:10]

    # Mark notifications as read
    meeting.notifications.filter(recipient=user, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )

    can_edit     = (user.can_edit_meeting or user.is_superuser) and meeting.status in ['SCHEDULED', 'IN_PROGRESS']
    can_complete = (user.can_close_meeting or user.is_superuser) and meeting.status in ['SCHEDULED', 'IN_PROGRESS']
    can_cancel   = (user.can_create_meeting or user.is_superuser) and meeting.status in ['SCHEDULED']
    can_add_attendees = (user.can_create_meeting or user.is_superuser) and meeting.status in ['SCHEDULED', 'IN_PROGRESS']
    can_mark_attendance = (user.can_mark_meeting_attendance or user.is_superuser) and meeting.status in ['IN_PROGRESS', 'COMPLETED']
    can_add_action = (user.can_manage_meeting_action_items or user.is_superuser) and meeting.status in ['IN_PROGRESS', 'COMPLETED']
    can_publish_mom = (user.can_close_meeting or user.is_superuser) and meeting.status == 'COMPLETED' and not meeting.mom_published

    context = {
        'meeting': meeting,
        'attendees': attendees,
        'action_items': action_items,
        'notifications': notifications,
        'can_edit': can_edit,
        'can_complete': can_complete,
        'can_cancel': can_cancel,
        'can_add_attendees': can_add_attendees,
        'can_mark_attendance': can_mark_attendance,
        'can_add_action': can_add_action,
        'can_publish_mom': can_publish_mom,
        'open_actions': action_items.filter(status__in=['OPEN', 'IN_PROGRESS']).count(),
        'page_title': f'Meeting {meeting.meeting_number}',
    }
    return render(request, 'meetings/meeting_detail.html', context)


# ============================================================
# 5. MEETING EDIT
# ============================================================

@login_required
@meeting_access_required
def meeting_edit(request, pk):
    user = request.user
    user_plants = user.get_all_plants()

    meeting = get_object_or_404(SafetyMeeting, pk=pk, plant__in=user_plants)

    if not (user.can_edit_meeting or user.is_superuser):
        messages.error(request, "You don't have permission to edit meetings.")
        return redirect('meetings:meeting_detail', pk=pk)

    if meeting.status in ['COMPLETED', 'CANCELLED']:
        messages.error(request, f"Cannot edit a {meeting.get_status_display()} meeting.")
        return redirect('meetings:meeting_detail', pk=pk)

    if request.method == 'POST':
        form = SafetyMeetingForm(request.POST, request.FILES, instance=meeting, user=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Meeting updated successfully.")
            return redirect('meetings:meeting_detail', pk=pk)
    else:
        form = SafetyMeetingForm(instance=meeting, user=user)

    context = {
        'form': form,
        'meeting': meeting,
        'user_assigned_plants': user_plants,
        'page_title': f'Edit Meeting {meeting.meeting_number}',
    }
    return render(request, 'meetings/meeting_edit.html', context)


# ============================================================
# 6. ADD ATTENDEES
# ============================================================

@login_required
@meeting_access_required
def add_attendees(request, pk):
    user = request.user
    user_plants = user.get_all_plants()

    meeting = get_object_or_404(SafetyMeeting, pk=pk, plant__in=user_plants)

    if not (user.can_create_meeting or user.is_superuser):
        messages.error(request, "You don't have permission to add attendees.")
        return redirect('meetings:meeting_detail', pk=pk)

    if meeting.status in ['COMPLETED', 'CANCELLED']:
        messages.error(request, "Cannot add attendees to a completed/cancelled meeting.")
        return redirect('meetings:meeting_detail', pk=pk)

    if request.method == 'POST':
        form = AddAttendeesForm(request.POST, meeting=meeting)
        if form.is_valid():
            employees = form.cleaned_data['employees']
            added = 0
            for emp in employees:
                attendee, created = MeetingAttendee.objects.get_or_create(
                    meeting=meeting,
                    employee=emp,
                    defaults={'attendance_status': 'INVITED'}
                )
                if created:
                    added += 1
                    # Notify the invited employee
                    _send_notification(
                        recipient=emp,
                        meeting=meeting,
                        notification_type='MEETING_SCHEDULED',
                        title=f"You are invited to: {meeting.title}",
                        message=(
                            f"You have been invited to attend a safety meeting.\n"
                            f"Meeting No: {meeting.meeting_number}\n"
                            f"Date: {meeting.scheduled_date.strftime('%d %b %Y')} at {meeting.scheduled_time.strftime('%I:%M %p')}\n"
                            f"Venue: {meeting.venue_details or meeting.location}"
                        ),
                    )
            messages.success(request, f"{added} attendee(s) added and notified.")
            return redirect('meetings:meeting_detail', pk=pk)
    else:
        form = AddAttendeesForm(meeting=meeting)

    context = {
        'form': form,
        'meeting': meeting,
        'page_title': f'Add Attendees — {meeting.meeting_number}',
    }
    return render(request, 'meetings/add_attendees.html', context)


# ============================================================
# 7. MARK ATTENDANCE
# ============================================================

@login_required
@meeting_access_required
def mark_attendance(request, pk):
    user = request.user
    user_plants = user.get_all_plants()

    meeting = get_object_or_404(SafetyMeeting, pk=pk, plant__in=user_plants)

    if not (user.can_mark_meeting_attendance or user.is_superuser):
        messages.error(request, "You don't have permission to mark attendance.")
        return redirect('meetings:meeting_detail', pk=pk)

    if meeting.status == 'CANCELLED':
        messages.error(request, "Cannot mark attendance for a cancelled meeting.")
        return redirect('meetings:meeting_detail', pk=pk)

    if request.method == 'POST':
        formset = MeetingAttendeeFormSet(request.POST, instance=meeting)
        if formset.is_valid():
            instances = formset.save(commit=False)
            for attendee in instances:
                attendee.marked_by = user
                attendee.marked_at = timezone.now()
                attendee.save()

                # Notify attendee
                if attendee.attendance_status == 'PRESENT':
                    _send_notification(
                        recipient=attendee.employee,
                        meeting=meeting,
                        notification_type='ATTENDANCE_MARKED',
                        title=f"Attendance Marked — {meeting.meeting_number}",
                        message=f"Your attendance has been marked as Present for meeting {meeting.meeting_number}.",
                    )

            # Move to IN_PROGRESS if still SCHEDULED
            if meeting.status == 'SCHEDULED':
                meeting.status = 'IN_PROGRESS'
                meeting.save(update_fields=['status'])

            messages.success(request, "Attendance marked successfully.")
            return redirect('meetings:meeting_detail', pk=pk)
    else:
        formset = MeetingAttendeeFormSet(instance=meeting)

    context = {
        'meeting': meeting,
        'formset': formset,
        'page_title': f'Mark Attendance — {meeting.meeting_number}',
    }
    return render(request, 'meetings/mark_attendance.html', context)


# ============================================================
# 8. COMPLETE MEETING (Record MOM)
# ============================================================

@login_required
@meeting_access_required
def meeting_complete(request, pk):
    user = request.user
    user_plants = user.get_all_plants()

    meeting = get_object_or_404(SafetyMeeting, pk=pk, plant__in=user_plants)

    if not (user.can_close_meeting or user.is_superuser):
        messages.error(request, "You don't have permission to complete meetings.")
        return redirect('meetings:meeting_detail', pk=pk)

    can, reason = meeting.can_be_completed
    if not can:
        messages.error(request, reason)
        return redirect('meetings:meeting_detail', pk=pk)

    if request.method == 'POST':
        form = SafetyMeetingCompleteForm(request.POST, request.FILES, instance=meeting)
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.status = 'COMPLETED'
            if not meeting.actual_date:
                meeting.actual_date = datetime.date.today()
            meeting.save()
            messages.success(request, f"Meeting {meeting.meeting_number} marked as Completed.")
            return redirect('meetings:meeting_detail', pk=pk)
    else:
        form = SafetyMeetingCompleteForm(instance=meeting)

    context = {
        'form': form,
        'meeting': meeting,
        'page_title': f'Complete Meeting — {meeting.meeting_number}',
    }
    return render(request, 'meetings/meeting_complete.html', context)


# ============================================================
# 9. PUBLISH MOM
#    Notifies all attendees with the minutes of meeting
# ============================================================

@login_required
@meeting_access_required
def publish_mom(request, pk):
    user = request.user
    user_plants = user.get_all_plants()

    meeting = get_object_or_404(SafetyMeeting, pk=pk, plant__in=user_plants)

    if not (user.can_close_meeting or user.is_superuser):
        messages.error(request, "You don't have permission to publish MOM.")
        return redirect('meetings:meeting_detail', pk=pk)

    if meeting.status != 'COMPLETED':
        messages.error(request, "MOM can only be published for Completed meetings.")
        return redirect('meetings:meeting_detail', pk=pk)

    if meeting.mom_published:
        messages.warning(request, "MOM has already been published.")
        return redirect('meetings:meeting_detail', pk=pk)

    if not meeting.minutes_of_meeting.strip():
        messages.error(request, "Please record the Minutes of Meeting before publishing.")
        return redirect('meetings:meeting_complete', pk=pk)

    if request.method == 'POST':
        meeting.mom_published    = True
        meeting.mom_published_at = timezone.now()
        meeting.save(update_fields=['mom_published', 'mom_published_at'])

        # Notify all attendees
        for attendee in meeting.attendees.select_related('employee'):
            _send_notification(
                recipient=attendee.employee,
                meeting=meeting,
                notification_type='MOM_PUBLISHED',
                title=f"MOM Published — {meeting.meeting_number}",
                message=(
                    f"Minutes of Meeting for '{meeting.title}' have been published.\n"
                    f"Meeting No: {meeting.meeting_number}\n"
                    f"Date: {meeting.actual_date or meeting.scheduled_date}\n"
                    f"Please review the meeting minutes and action items assigned to you."
                ),
            )

        messages.success(request, f"MOM published. All {meeting.attendees.count()} attendees have been notified.")
        return redirect('meetings:meeting_detail', pk=pk)

    context = {
        'meeting': meeting,
        'page_title': f'Publish MOM — {meeting.meeting_number}',
    }
    return render(request, 'meetings/publish_mom_confirm.html', context)


# ============================================================
# 10. CANCEL MEETING
# ============================================================

@login_required
@meeting_access_required
def meeting_cancel(request, pk):
    user = request.user
    user_plants = user.get_all_plants()

    meeting = get_object_or_404(SafetyMeeting, pk=pk, plant__in=user_plants)

    if not (user.can_create_meeting or user.is_superuser):
        messages.error(request, "You don't have permission to cancel meetings.")
        return redirect('meetings:meeting_detail', pk=pk)

    if meeting.status != 'SCHEDULED':
        messages.error(request, "Only Scheduled meetings can be cancelled.")
        return redirect('meetings:meeting_detail', pk=pk)

    if request.method == 'POST':
        form = SafetyMeetingCancelForm(request.POST, instance=meeting)
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.status = 'CANCELLED'
            meeting.save()

            # Notify all invited attendees
            for attendee in meeting.attendees.select_related('employee'):
                _send_notification(
                    recipient=attendee.employee,
                    meeting=meeting,
                    notification_type='MEETING_CANCELLED',
                    title=f"Meeting Cancelled — {meeting.meeting_number}",
                    message=(
                        f"The safety meeting '{meeting.title}' scheduled on "
                        f"{meeting.scheduled_date.strftime('%d %b %Y')} has been cancelled.\n"
                        f"Reason: {meeting.cancelled_reason}"
                    ),
                )

            messages.success(request, f"Meeting {meeting.meeting_number} cancelled.")
            return redirect('meetings:meeting_list')
    else:
        form = SafetyMeetingCancelForm(instance=meeting)

    context = {
        'form': form,
        'meeting': meeting,
        'page_title': f'Cancel Meeting — {meeting.meeting_number}',
    }
    return render(request, 'meetings/meeting_cancel.html', context)


# ============================================================
# 11. ACTION ITEM — ADD
# ============================================================

@login_required
@meeting_access_required
def add_action_item(request, pk):
    user = request.user
    user_plants = user.get_all_plants()

    meeting = get_object_or_404(SafetyMeeting, pk=pk, plant__in=user_plants)

    if not (user.can_manage_meeting_action_items or user.is_superuser):
        messages.error(request, "You don't have permission to add action items.")
        return redirect('meetings:meeting_detail', pk=pk)

    if meeting.status == 'CANCELLED':
        messages.error(request, "Cannot add action items to a cancelled meeting.")
        return redirect('meetings:meeting_detail', pk=pk)

    if request.method == 'POST':
        form = MeetingActionItemForm(request.POST, meeting=meeting)
        if form.is_valid():
            action = form.save(commit=False)
            action.meeting     = meeting
            action.assigned_by = user
            action.status      = 'OPEN'
            action.save()

            # Notify the assigned person
            if action.assigned_to:
                _send_notification(
                    recipient=action.assigned_to,
                    meeting=meeting,
                    action_item=action,
                    notification_type='ACTION_ASSIGNED',
                    title=f"Action Item Assigned — {meeting.meeting_number}",
                    message=(
                        f"An action item has been assigned to you from meeting {meeting.meeting_number}.\n"
                        f"Action: {action.description[:200]}\n"
                        f"Priority: {action.get_priority_display()}\n"
                        f"Due Date: {action.due_date.strftime('%d %b %Y')}"
                    ),
                )

            messages.success(request, "Action item added and assignee notified.")
            return redirect('meetings:meeting_detail', pk=pk)
    else:
        form = MeetingActionItemForm(meeting=meeting)

    context = {
        'form': form,
        'meeting': meeting,
        'page_title': f'Add Action Item — {meeting.meeting_number}',
    }
    return render(request, 'meetings/add_action_item.html', context)


# ============================================================
# 12. ACTION ITEM — CLOSE
# ============================================================

@login_required
@meeting_access_required
def close_action_item(request, action_pk):
    user = request.user

    action = get_object_or_404(
        MeetingActionItem.objects.select_related('meeting__plant'),
        pk=action_pk,
        meeting__plant__in=user.get_all_plants()
    )

    # Only assigned person or admin can close
    if not (action.assigned_to == user or user.can_manage_meeting_action_items or user.is_superuser):
        messages.error(request, "You can only close action items assigned to you.")
        return redirect('meetings:meeting_detail', pk=action.meeting.pk)

    if action.status == 'CLOSED':
        messages.warning(request, "This action item is already closed.")
        return redirect('meetings:meeting_detail', pk=action.meeting.pk)

    if request.method == 'POST':
        form = ActionItemCloseForm(request.POST, request.FILES, instance=action)
        if form.is_valid():
            action = form.save(commit=False)
            action.status    = 'CLOSED'
            action.closed_by = user
            action.closed_at = timezone.now()
            action.save()

            # Notify the person who raised the action (assigned_by)
            if action.assigned_by and action.assigned_by != user:
                _send_notification(
                    recipient=action.assigned_by,
                    meeting=action.meeting,
                    action_item=action,
                    notification_type='ACTION_CLOSED',
                    title=f"Action Item Closed — {action.meeting.meeting_number}",
                    message=(
                        f"An action item from meeting {action.meeting.meeting_number} has been closed by "
                        f"{user.get_full_name()}.\n"
                        f"Action: {action.description[:200]}\n"
                        f"Closure Remarks: {action.closure_remarks}"
                    ),
                )

            messages.success(request, "Action item closed successfully.")
            return redirect('meetings:meeting_detail', pk=action.meeting.pk)
    else:
        form = ActionItemCloseForm(instance=action)

    context = {
        'form': form,
        'action': action,
        'meeting': action.meeting,
        'page_title': 'Close Action Item',
    }
    return render(request, 'meetings/close_action_item.html', context)


# ============================================================
# 13. ESCALATE ACTION TO HAZARD REPORT
# ============================================================

@login_required
@meeting_access_required
def escalate_to_hazard(request, action_pk):
    """
    Converts a Meeting Action Item into a Hazard Report.
    Creates the HazardReport with pre-filled description from the action item.
    Links back via action.hazard_report FK.
    """
    user = request.user

    action = get_object_or_404(
        MeetingActionItem.objects.select_related('meeting__plant', 'meeting__location'),
        pk=action_pk,
        meeting__plant__in=user.get_all_plants()
    )

    if action.escalated_to_hazard:
        messages.warning(request, "This action item has already been escalated to a Hazard Report.")
        return redirect('meetings:meeting_detail', pk=action.meeting.pk)

    if not (user.can_manage_meeting_action_items or user.is_superuser):
        messages.error(request, "You don't have permission to escalate action items.")
        return redirect('meetings:meeting_detail', pk=action.meeting.pk)

    if request.method == 'POST':
        try:
            from apps.hazards.models import HazardReport

            hazard = HazardReport.objects.create(
                # Pre-fill from the meeting context
                plant=action.meeting.plant,
                zone=action.meeting.zone,
                location=action.meeting.location,
                sublocation=action.meeting.sublocation,
                description=(
                    f"[Escalated from Safety Meeting {action.meeting.meeting_number}]\n\n"
                    f"{action.description}"
                ),
                reported_by=user,
                # Default to medium risk — Safety Officer will update
                risk_level='MEDIUM',
                status='OPEN',
                source='MEETING',
            )

            # Link back
            action.hazard_report      = hazard
            action.escalated_to_hazard = True
            action.save(update_fields=['hazard_report', 'escalated_to_hazard'])

            # Notify assigned person
            if action.assigned_to:
                _send_notification(
                    recipient=action.assigned_to,
                    meeting=action.meeting,
                    action_item=action,
                    notification_type='ESCALATED_TO_HAZARD',
                    title=f"Action Escalated to Hazard — {action.meeting.meeting_number}",
                    message=(
                        f"The action item assigned to you from meeting {action.meeting.meeting_number} "
                        f"has been escalated to a Hazard Report (#{hazard.report_number}).\n"
                        f"Please review and take corrective action."
                    ),
                )

            messages.success(
                request,
                f"Escalated to Hazard Report {hazard.report_number}. "
                f"You can now manage it from the Hazard module."
            )

        except Exception as e:
            messages.error(request, f"Failed to escalate: {str(e)}")

        return redirect('meetings:meeting_detail', pk=action.meeting.pk)

    context = {
        'action': action,
        'meeting': action.meeting,
        'page_title': 'Escalate to Hazard Report',
    }
    return render(request, 'meetings/escalate_confirm.html', context)


# ============================================================
# 14. MY MEETINGS
#    Employee view — meetings I am invited to
# ============================================================

@login_required
@meeting_access_required
def my_meetings(request):
    user = request.user

    # Meetings where I am an attendee
    my_attendances = MeetingAttendee.objects.filter(
        employee=user
    ).select_related('meeting__plant', 'meeting__location', 'meeting__chairperson')

    upcoming = [
        a for a in my_attendances
        if a.meeting.status == 'SCHEDULED'
        and a.meeting.scheduled_date >= datetime.date.today()
    ]

    past = [
        a for a in my_attendances
        if a.meeting.status == 'COMPLETED'
    ]

    # Action items assigned to me
    my_actions = MeetingActionItem.objects.filter(
        assigned_to=user
    ).select_related('meeting').order_by('due_date')

    context = {
        'upcoming_meetings': upcoming,
        'past_meetings': past,
        'my_actions': my_actions,
        'open_actions': my_actions.filter(status__in=['OPEN', 'IN_PROGRESS']),
        'page_title': 'My Safety Meetings',
    }
    return render(request, 'meetings/my_meetings.html', context)


# ============================================================
# 15. NOTIFICATIONS
# ============================================================

@login_required
@meeting_access_required
def notifications(request):
    user = request.user
    notifs = MeetingNotification.objects.filter(recipient=user).order_by('-created_at')

    # Mark all as read
    notifs.filter(is_read=False).update(is_read=True, read_at=timezone.now())

    context = {
        'notifications': notifs[:50],
        'page_title': 'Meeting Notifications',
    }
    return render(request, 'meetings/notifications.html', context)


# ============================================================
# 16. AJAX VIEWS — same pattern as your other modules
# ============================================================

@login_required
def ajax_get_zones(request):
    plant_id = request.GET.get('plant_id')
    if not plant_id:
        return JsonResponse({'zones': []})
    from apps.organizations.models import Zone
    zones = Zone.objects.filter(plant_id=plant_id, is_active=True).values('id', 'name')
    return JsonResponse({'zones': list(zones)})


@login_required
def ajax_get_locations(request):
    zone_id = request.GET.get('zone_id')
    if not zone_id:
        return JsonResponse({'locations': []})
    from apps.organizations.models import Location
    locations = Location.objects.filter(zone_id=zone_id, is_active=True).values('id', 'name')
    return JsonResponse({'locations': list(locations)})


@login_required
def ajax_get_sublocations(request):
    location_id = request.GET.get('location_id')
    if not location_id:
        return JsonResponse({'sublocations': []})
    from apps.organizations.models import SubLocation
    sublocations = SubLocation.objects.filter(location_id=location_id, is_active=True).values('id', 'name')
    return JsonResponse({'sublocations': list(sublocations)})


@login_required
def ajax_get_plant_employees(request):
    """Returns employees for a given plant — used in attendee selection"""
    plant_id = request.GET.get('plant_id')
    if not plant_id:
        return JsonResponse({'employees': []})
    from django.contrib.auth import get_user_model
    User = get_user_model()
    employees = User.objects.filter(
        is_active=True,
        assigned_plants=plant_id
    ).distinct().values('id', 'first_name', 'last_name', 'employee_id')
    data = [
        {
            'id': e['id'],
            'name': f"{e['first_name']} {e['last_name']}",
            'employee_id': e['employee_id'] or '',
        }
        for e in employees
    ]
    return JsonResponse({'employees': data})