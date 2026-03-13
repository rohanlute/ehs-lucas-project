import datetime
import json
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView,
    TemplateView, DeleteView, View, FormView
)
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q, Count, Avg
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.organizations.models import Plant, Zone, Location, SubLocation, Department
from .models import (
    TrainingTopic, TrainingRequirement, TrainingSession,
    TrainingParticipant, TrainingRecord, TrainingNotification
)
from .forms import (
    TrainingTopicForm, TrainingRequirementForm, TrainingSessionForm,
    TrainingParticipantFormSet, TrainingRecordManualForm,
    TrainingSessionCompleteForm, TrainingSessionCancelForm
)

User = get_user_model()


# ============================================================
# HELPER MIXIN — Role-based queryset (like your IncidentListView)
# ============================================================

class TrainingAccessMixin(LoginRequiredMixin):
    """
    Base mixin for training views.
    Checks can_access_training_module permission.
    Exactly like your pattern in other modules.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not (
            request.user.is_superuser or
            getattr(request.user, 'can_access_training_module', False) or
            (hasattr(request.user, 'role') and request.user.role and
             request.user.role.name in ['ADMIN', 'SAFETY OFFICER', 'PLANT HEAD', 'HOD'])
        ):
            messages.error(request, "You don't have permission to access the Training module.")
            return redirect('dashboards:home')
        return super().dispatch(request, *args, **kwargs)

    def get_base_sessions_queryset(self):
        """
        Role-based base queryset — exactly like your IncidentListView.get_queryset()
        """
        user = self.request.user
        queryset = TrainingSession.objects.select_related(
            'topic', 'plant', 'zone', 'location', 'created_by'
        ).order_by('-scheduled_date', '-scheduled_time')

        if user.is_superuser or (
            hasattr(user, 'role') and user.role and user.role.name == 'ADMIN'
        ):
            return queryset
        elif hasattr(user, 'role') and user.role and user.role.name == 'EMPLOYEE':
            # Employee sees only sessions they are invited to
            return queryset.filter(participants__employee=user)
        elif user.plant:
            return queryset.filter(plant=user.plant)
        else:
            return queryset.filter(created_by=user)


# ============================================================
# 1. TRAINING TOPIC VIEWS (like your IncidentType views)
# ============================================================

class TrainingTopicListView(TrainingAccessMixin, ListView):
    """List all training topics — like IncidentTypeListView"""
    model = TrainingTopic
    template_name = 'training/topic_list.html'
    context_object_name = 'topics'
    paginate_by = 20

    def get_queryset(self):
        queryset = TrainingTopic.objects.annotate(
            session_count=Count('sessions')
        ).order_by('name')

        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )

        category = self.request.GET.get('category', '')
        if category:
            queryset = queryset.filter(category=category)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['category_choices'] = TrainingTopic.CATEGORY_CHOICES
        context['total_topics'] = TrainingTopic.objects.filter(is_active=True).count()
        return context


class TrainingTopicCreateView(TrainingAccessMixin, CreateView):
    """Create training topic — like IncidentTypeCreateView"""
    model = TrainingTopic
    form_class = TrainingTopicForm
    template_name = 'training/topic_form.html'
    success_url = reverse_lazy('training:topic_list')

    def dispatch(self, request, *args, **kwargs):
        # Only admin/safety officer can manage topics
        if not (
            request.user.is_superuser or
            getattr(request.user, 'can_manage_training_topics', False) or
            (hasattr(request.user, 'role') and request.user.role and
             request.user.role.name in ['ADMIN', 'SAFETY OFFICER'])
        ):
            messages.error(request, "You don't have permission to manage training topics.")
            return redirect('training:topic_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        topic = form.save(commit=False)
        topic.created_by = self.request.user
        topic.save()
        messages.success(self.request, f'Training Topic "{topic.name}" created successfully!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'Create'
        return context


class TrainingTopicUpdateView(TrainingAccessMixin, UpdateView):
    """Update training topic"""
    model = TrainingTopic
    form_class = TrainingTopicForm
    template_name = 'training/topic_form.html'
    success_url = reverse_lazy('training:topic_list')

    def dispatch(self, request, *args, **kwargs):
        if not (
            request.user.is_superuser or
            getattr(request.user, 'can_manage_training_topics', False) or
            (hasattr(request.user, 'role') and request.user.role and
             request.user.role.name in ['ADMIN', 'SAFETY OFFICER'])
        ):
            messages.error(request, "You don't have permission to edit training topics.")
            return redirect('training:topic_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f'Training Topic "{self.object.name}" updated successfully!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'Update'
        context['topic'] = self.object
        return context


# ============================================================
# 2. TRAINING SESSION VIEWS (like your Incident views)
# ============================================================

class TrainingSessionDashboardView(TrainingAccessMixin, TemplateView):
    """
    Training Dashboard — like IncidentDashboardView
    Shows stats, upcoming sessions, compliance overview
    """
    template_name = 'training/dashboard.html'

    # ============================================================
# REPLACE get_context_data inside TrainingSessionDashboardView
# Also ensure these imports exist at top of training_views.py:
#   from django.db.models.functions import TruncMonth
#   import json  (already present)
# ============================================================

    def get_context_data(self, **kwargs):
        from django.db.models.functions import TruncMonth

        context = super().get_context_data(**kwargs)
        user  = self.request.user
        today = timezone.now().date()

        # ── Role-based base querysets (unchanged from original) ──
        if user.is_superuser or (
            hasattr(user, 'role') and user.role and user.role.name == 'ADMIN'
        ):
            sessions     = TrainingSession.objects.all()
            records      = TrainingRecord.objects.all()
            participants = TrainingParticipant.objects.all()
        elif user.plant:
            sessions     = TrainingSession.objects.filter(plant=user.plant)
            records      = TrainingRecord.objects.filter(employee__plant=user.plant)
            participants = TrainingParticipant.objects.filter(session__plant=user.plant)
        else:
            sessions     = TrainingSession.objects.filter(participants__employee=user)
            records      = TrainingRecord.objects.filter(employee=user)
            participants = TrainingParticipant.objects.filter(employee=user)

        # ════════════════════════════
        # STAT CARDS
        # ════════════════════════════
        total_sessions     = sessions.count()
        scheduled_sessions = sessions.filter(status='SCHEDULED').count()
        completed_sessions = sessions.filter(status='COMPLETED').count()
        cancelled_sessions = sessions.filter(status='CANCELLED').count()
        ongoing_sessions   = sessions.filter(status='ONGOING').count()

        overdue_sessions = sessions.filter(
            status='SCHEDULED', scheduled_date__lt=today
        ).count()

        this_month_sessions = sessions.filter(
            scheduled_date__month=today.month,
            scheduled_date__year=today.year
        ).count()

        # Certificate stats
        active_certs   = records.filter(status='ACTIVE').count()
        expiring_soon  = records.filter(
            status='ACTIVE',
            valid_until__lte=today + datetime.timedelta(days=30),
            valid_until__gte=today
        ).count()
        expired_certs  = records.filter(valid_until__lt=today).count()

        # Overall pass rate
        total_assessed = participants.filter(
            attendance_status='PRESENT',
            session__topic__passing_score__gt=0
        ).count()
        total_passed = participants.filter(
            attendance_status='PRESENT',
            session__topic__passing_score__gt=0,
            passed=True
        ).count()
        overall_pass_rate = round((total_passed / total_assessed * 100), 1) if total_assessed else 0

        # ════════════════════════════
        # LISTS
        # ════════════════════════════
        upcoming_sessions = sessions.filter(
            status='SCHEDULED',
            scheduled_date__gte=today,
            scheduled_date__lte=today + datetime.timedelta(days=30)
        ).select_related('topic', 'plant', 'location').order_by('scheduled_date')[:5]

        recent_sessions = sessions.filter(
            status='COMPLETED'
        ).select_related('topic', 'plant').order_by('-actual_date')[:5]

        expiring_records = records.filter(
            status='ACTIVE',
            valid_until__lte=today + datetime.timedelta(days=30),
            valid_until__gte=today
        ).select_related('employee', 'topic').order_by('valid_until')[:10]

        overdue_session_list = sessions.filter(
            status='SCHEDULED',
            scheduled_date__lt=today
        ).select_related('topic', 'plant').order_by('scheduled_date')[:5]

        unread_count = TrainingNotification.objects.filter(
            recipient=user, is_read=False
        ).count()

        # ════════════════════════════
        # CHART DATA
        # ════════════════════════════

        # 1. Monthly Trend — last 6 months (Line)
        six_months_ago = (today.replace(day=1) - datetime.timedelta(days=150))
        monthly_data = (
            sessions
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

        # 2. Sessions by Category (Doughnut)
        category_data = (
            sessions
            .values('topic__category')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        category_map    = dict(TrainingTopic.CATEGORY_CHOICES)
        category_labels = [
            category_map.get(d['topic__category'], d['topic__category'] or 'Unknown')
            for d in category_data
        ]
        category_counts = [d['count'] for d in category_data]

        # 3. Sessions by Training Mode (Bar)
        mode_data = (
            sessions
            .values('training_mode')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        mode_map    = dict(TrainingSession.TRAINING_MODE_CHOICES)
        mode_labels = [mode_map.get(d['training_mode'], d['training_mode']) for d in mode_data]
        mode_counts = [d['count'] for d in mode_data]

        # 4. Attendance Rate — last 10 completed sessions (Bar)
        last_10_sessions  = list(sessions.filter(status='COMPLETED').order_by('-actual_date')[:10])
        att_labels = [s.session_number for s in last_10_sessions]
        att_rates  = [s.attendance_percentage for s in last_10_sessions]

        # 5. Certificate Status (Doughnut)
        cert_labels = ['Active', 'Expiring (30d)', 'Expired']
        cert_counts = [
            max(active_certs - expiring_soon, 0),
            expiring_soon,
            expired_certs,
        ]

        # 6. Top 8 Topics by session count (Horizontal Bar)
        topic_data = (
            sessions
            .values('topic__name')
            .annotate(
                total=Count('id'),
                completed=Count('id', filter=Q(status='COMPLETED')),
            )
            .order_by('-total')[:8]
        )
        topic_labels    = [d['topic__name'] for d in topic_data]
        topic_totals    = [d['total'] for d in topic_data]
        topic_completed = [d['completed'] for d in topic_data]

        # 7. Pass Rate per Topic — last 90 days (Bar)
        ninety_days_ago = today - datetime.timedelta(days=90)
        pass_rate_data = (
            participants
            .filter(
                session__status='COMPLETED',
                session__actual_date__gte=ninety_days_ago,
                attendance_status='PRESENT',
                session__topic__passing_score__gt=0,
            )
            .values('session__topic__name')
            .annotate(
                total=Count('id'),
                passed=Count('id', filter=Q(passed=True)),
            )
            .order_by('-total')[:8]
        )
        passrate_labels = [d['session__topic__name'] for d in pass_rate_data]
        passrate_values = [
            round(d['passed'] / d['total'] * 100, 1) if d['total'] else 0
            for d in pass_rate_data
        ]

        # ── Assign to context ──
        context.update({
            # Stat cards
            'total_sessions':       total_sessions,
            'scheduled_sessions':   scheduled_sessions,
            'completed_sessions':   completed_sessions,
            'cancelled_sessions':   cancelled_sessions,
            'ongoing_sessions':     ongoing_sessions,
            'overdue_sessions':     overdue_sessions,
            'this_month_sessions':  this_month_sessions,
            'active_certs':         active_certs,
            'expiring_soon':        expiring_soon,
            'expired_certs':        expired_certs,
            'overall_pass_rate':    overall_pass_rate,

            # Lists
            'upcoming_sessions':    upcoming_sessions,
            'recent_sessions':      recent_sessions,
            'expiring_records':     expiring_records,
            'overdue_session_list': overdue_session_list,
            'unread_count':         unread_count,

            # Chart JSON
            'monthly_labels':       json.dumps(monthly_labels),
            'monthly_totals':       json.dumps(monthly_totals),
            'monthly_completed':    json.dumps(monthly_completed),
            'category_labels':      json.dumps(category_labels),
            'category_counts':      json.dumps(category_counts),
            'mode_labels':          json.dumps(mode_labels),
            'mode_counts':          json.dumps(mode_counts),
            'att_labels':           json.dumps(att_labels),
            'att_rates':            json.dumps(att_rates),
            'cert_labels':          json.dumps(cert_labels),
            'cert_counts':          json.dumps(cert_counts),
            'topic_labels':         json.dumps(topic_labels),
            'topic_totals':         json.dumps(topic_totals),
            'topic_completed':      json.dumps(topic_completed),
            'passrate_labels':      json.dumps(passrate_labels),
            'passrate_values':      json.dumps(passrate_values),

            'page_title': 'Training Management Dashboard',
        })
        return context


class TrainingSessionListView(TrainingAccessMixin, ListView):
    """
    List all training sessions — like IncidentListView
    Supports search + filters
    """
    model = TrainingSession
    template_name = 'training/session_list.html'
    context_object_name = 'sessions'
    paginate_by = 20

    def get_queryset(self):
        queryset = self.get_base_sessions_queryset()

        # Search
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(session_number__icontains=search) |
                Q(topic__name__icontains=search) |
                Q(trainer_name__icontains=search)
            )

        # Filters
        topic = self.request.GET.get('topic', '')
        if topic:
            queryset = queryset.filter(topic_id=topic)

        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)

        plant = self.request.GET.get('plant', '')
        if plant:
            queryset = queryset.filter(plant_id=plant)

        training_mode = self.request.GET.get('training_mode', '')
        if training_mode:
            queryset = queryset.filter(training_mode=training_mode)

        date_from = self.request.GET.get('date_from', '')
        if date_from:
            queryset = queryset.filter(scheduled_date__gte=date_from)

        date_to = self.request.GET.get('date_to', '')
        if date_to:
            queryset = queryset.filter(scheduled_date__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['topics'] = TrainingTopic.objects.filter(is_active=True).order_by('name')
        context['plants'] = Plant.objects.filter(is_active=True)
        context['status_choices'] = TrainingSession.STATUS_CHOICES
        context['mode_choices'] = TrainingSession.TRAINING_MODE_CHOICES
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_topic'] = self.request.GET.get('topic', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_plant'] = self.request.GET.get('plant', '')
        context['selected_mode'] = self.request.GET.get('training_mode', '')
        return context


class TrainingSessionCreateView(TrainingAccessMixin, CreateView):
    """
    Create training session — like IncidentCreateView
    Handles location assignment (single vs multiple) same logic
    """
    model = TrainingSession
    form_class = TrainingSessionForm
    template_name = 'training/session_create.html'

    def dispatch(self, request, *args, **kwargs):
        if not (
            request.user.is_superuser or
            getattr(request.user, 'can_create_training_session', False) or
            (hasattr(request.user, 'role') and request.user.role and
             request.user.role.name in ['ADMIN', 'SAFETY OFFICER', 'PLANT HEAD'])
        ):
            messages.error(request, "You don't have permission to create training sessions.")
            return redirect('training:session_list')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        """
        Exactly same location context logic as your IncidentCreateView
        """
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['user_assigned_plants'] = user.assigned_plants.filter(is_active=True)

        if context['user_assigned_plants'].count() == 1:
            plant = context['user_assigned_plants'].first()
            context['user_assigned_zones'] = user.assigned_zones.filter(is_active=True, plant=plant)
            if context['user_assigned_zones'].count() == 1:
                zone = context['user_assigned_zones'].first()
                context['user_assigned_locations'] = user.assigned_locations.filter(is_active=True, zone=zone)
                if context['user_assigned_locations'].count() == 1:
                    location = context['user_assigned_locations'].first()
                    context['user_assigned_sublocations'] = user.assigned_sublocations.filter(is_active=True, location=location)
                else:
                    context['user_assigned_sublocations'] = user.assigned_sublocations.none()
            else:
                context['user_assigned_locations'] = user.assigned_locations.none()
                context['user_assigned_sublocations'] = user.assigned_sublocations.none()
        else:
            context['user_assigned_zones'] = user.assigned_zones.none()
            context['user_assigned_locations'] = user.assigned_locations.none()
            context['user_assigned_sublocations'] = user.assigned_sublocations.none()

        context['active_topics'] = TrainingTopic.objects.filter(is_active=True).order_by('name')
        context['cancel_url'] = (
            self.request.GET.get('next') or
            self.request.META.get('HTTP_REFERER') or '/'
        )
        return context

    def form_valid(self, form):
        session = form.save(commit=False)
        session.created_by = self.request.user
        user = self.request.user

        # Single-assignment location logic — exactly like your IncidentCreateView.form_valid()
        if user.assigned_plants.count() == 1 and not form.cleaned_data.get('plant'):
            session.plant = user.assigned_plants.first()
        if user.assigned_zones.count() == 1 and not form.cleaned_data.get('zone'):
            session.zone = user.assigned_zones.first()
        if user.assigned_locations.count() == 1 and not form.cleaned_data.get('location'):
            session.location = user.assigned_locations.first()
        if user.assigned_sublocations.count() == 1 and not form.cleaned_data.get('sublocation'):
            session.sublocation = user.assigned_sublocations.first()

        session.save()
        self.object = session

        # Send notifications to invited participants
        try:
            from apps.notifications.services import NotificationService
            NotificationService.notify(
                content_object=self.object,
                notification_type='SESSION_SCHEDULED',
                module='TRAINING'
            )
        except Exception as e:
            print(f"Training session notification error: {e}")

        messages.success(
            self.request,
            f'Training Session "{session.session_number}" scheduled successfully!'
        )
        return redirect(reverse_lazy('training:session_detail', kwargs={'pk': session.pk}))

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class TrainingSessionDetailView(TrainingAccessMixin, DetailView):
    """
    Session detail — like IncidentDetailView
    Shows participants, records, action buttons
    """
    model = TrainingSession
    template_name = 'training/session_detail.html'
    context_object_name = 'session'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.object

        context['participants'] = session.participants.select_related('employee', 'marked_by').all()
        context['total_invited'] = session.total_invited
        context['total_present'] = session.total_present
        context['attendance_percentage'] = session.attendance_percentage

        # Can complete check — like your incident.can_be_closed
        can_complete, complete_message = session.can_be_completed
        context['can_complete'] = can_complete
        context['complete_message'] = complete_message

        # Training records generated from this session
        context['training_records'] = session.training_records.select_related('employee', 'topic').all()

        context['cancel_url'] = (
            self.request.GET.get('next') or
            self.request.META.get('HTTP_REFERER') or '/'
        )
        return context


class TrainingSessionUpdateView(TrainingAccessMixin, UpdateView):
    """Update session — like IncidentUpdateView"""
    model = TrainingSession
    form_class = TrainingSessionForm
    template_name = 'training/session_update.html'

    def dispatch(self, request, *args, **kwargs):
        session = get_object_or_404(TrainingSession, pk=kwargs['pk'])
        if session.status == 'COMPLETED':
            messages.error(request, "Completed sessions cannot be edited.")
            return redirect('training:session_detail', pk=session.pk)
        if not (
            request.user.is_superuser or
            getattr(request.user, 'can_edit_training_session', False) or
            (hasattr(request.user, 'role') and request.user.role and
             request.user.role.name in ['ADMIN', 'SAFETY OFFICER'])
        ):
            messages.error(request, "You don't have permission to edit sessions.")
            return redirect('training:session_detail', pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy('training:session_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, f'Session "{self.object.session_number}" updated successfully!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Same location context as CreateView
        context['user_assigned_plants'] = user.assigned_plants.filter(is_active=True)
        context['active_topics'] = TrainingTopic.objects.filter(is_active=True).order_by('name')
        context['cancel_url'] = (
            self.request.GET.get('next') or
            self.request.META.get('HTTP_REFERER') or '/'
        )
        return context


# ============================================================
# 3. ATTENDANCE MARKING VIEW
#    Like your InvestigationReportCreateView — handles formset
# ============================================================

class MarkAttendanceView(TrainingAccessMixin, View):
    """
    Mark attendance for a session.
    Like your InvestigationReportCreateView — handles per-employee records.
    """
    template_name = 'training/mark_attendance.html'

    def dispatch(self, request, *args, **kwargs):
        self.session = get_object_or_404(TrainingSession, pk=kwargs['pk'])

        if self.session.status == 'COMPLETED':
            messages.error(request, "Attendance already marked — session is completed.")
            return redirect('training:session_detail', pk=self.session.pk)

        if self.session.status == 'CANCELLED':
            messages.error(request, "Cannot mark attendance for a cancelled session.")
            return redirect('training:session_detail', pk=self.session.pk)

        if not (
            request.user.is_superuser or
            getattr(request.user, 'can_mark_training_attendance', False) or
            (hasattr(request.user, 'role') and request.user.role and
             request.user.role.name in ['ADMIN', 'SAFETY OFFICER', 'PLANT HEAD'])
        ):
            messages.error(request, "You don't have permission to mark attendance.")
            return redirect('training:session_detail', pk=self.session.pk)

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        participants = self.session.participants.select_related('employee').all()
        context = {
            'session': self.session,
            'participants': participants,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        participants = self.session.participants.select_related('employee').all()
        passing_score = self.session.topic.passing_score

        for participant in participants:
            attendance = request.POST.get(f'attendance_{participant.id}', 'ABSENT')
            score_raw = request.POST.get(f'score_{participant.id}', '').strip()
            remarks = request.POST.get(f'remarks_{participant.id}', '').strip()

            participant.attendance_status = attendance
            participant.remarks = remarks
            participant.marked_by = request.user
            participant.marked_at = timezone.now()

            # Assessment score handling
            if score_raw:
                try:
                    participant.assessment_score = int(score_raw)
                    participant.passed = participant.assessment_score >= passing_score
                except ValueError:
                    participant.assessment_score = None
                    participant.passed = (attendance == 'PRESENT' and passing_score == 0)
            else:
                participant.assessment_score = None
                # No assessment = present means passed
                participant.passed = (attendance == 'PRESENT' and passing_score == 0)

            participant.save()

        messages.success(request, f"Attendance marked for session {self.session.session_number}.")
        return redirect('training:session_detail', pk=self.session.pk)


# ============================================================
# 4. ADD PARTICIPANTS VIEW
# ============================================================

class AddParticipantsView(TrainingAccessMixin, View):
    """
    Add employees to a session as participants.
    Shows employees filtered by session's plant.
    """
    template_name = 'training/add_participants.html'

    def dispatch(self, request, *args, **kwargs):
        self.session = get_object_or_404(TrainingSession, pk=kwargs['pk'])
        if self.session.status in ['COMPLETED', 'CANCELLED']:
            messages.error(request, "Cannot add participants to a completed/cancelled session.")
            return redirect('training:session_detail', pk=self.session.pk)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # Get employees of the session's plant, exclude already added
        already_added = self.session.participants.values_list('employee_id', flat=True)
        available_employees = User.objects.filter(
            is_active=True,
            is_active_employee=True,
        ).filter(
            Q(plant=self.session.plant) | Q(assigned_plants=self.session.plant)
        ).exclude(id__in=already_added).select_related('department', 'role').distinct()

        # Search
        search = request.GET.get('search', '')
        if search:
            available_employees = available_employees.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(employee_id__icontains=search)
            )

        context = {
            'session': self.session,
            'available_employees': available_employees,
            'current_participants': self.session.participants.select_related('employee').all(),
            'search_query': search,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        employee_ids = request.POST.getlist('employee_ids')
        added_count = 0

        for emp_id in employee_ids:
            try:
                employee = User.objects.get(id=emp_id, is_active=True)
                # unique_together handles duplicates safely
                participant, created = TrainingParticipant.objects.get_or_create(
                    session=self.session,
                    employee=employee,
                    defaults={'attendance_status': 'INVITED'}
                )
                if created:
                    added_count += 1
            except User.DoesNotExist:
                continue

        # Send notification to newly added participants
        if added_count > 0:
            try:
                from apps.notifications.services import NotificationService
                NotificationService.notify(
                    content_object=self.session,
                    notification_type='SESSION_SCHEDULED',
                    module='TRAINING'
                )
            except Exception as e:
                print(f"Add participant notification error: {e}")

            messages.success(request, f"{added_count} participant(s) added successfully.")
        else:
            messages.info(request, "No new participants were added.")

        return redirect('training:session_detail', pk=self.session.pk)


# ============================================================
# 5. COMPLETE SESSION VIEW
#    Like your IncidentClosureView
# ============================================================

class CompleteSessionView(TrainingAccessMixin, UpdateView):
    """
    Mark session as COMPLETED and auto-generate TrainingRecords.
    Like your IncidentClosureView.
    """
    model = TrainingSession
    form_class = TrainingSessionCompleteForm
    template_name = 'training/session_complete.html'

    def dispatch(self, request, *args, **kwargs):
        session = get_object_or_404(TrainingSession, pk=kwargs['pk'])
        can_complete, message = session.can_be_completed
        if not can_complete:
            messages.error(request, f"Cannot complete session: {message}")
            return redirect('training:session_detail', pk=session.pk)

        if not (
            request.user.is_superuser or
            getattr(request.user, 'can_close_training_session', False) or
            (hasattr(request.user, 'role') and request.user.role and
             request.user.role.name in ['ADMIN', 'SAFETY OFFICER', 'PLANT HEAD'])
        ):
            messages.error(request, "You don't have permission to complete sessions.")
            return redirect('training:session_detail', pk=session.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        session = form.save(commit=False)
        session.status = 'COMPLETED'
        if not session.actual_date:
            session.actual_date = timezone.now().date()
        session.save()

        # Auto-create TrainingRecord for all PRESENT + PASSED participants
        # Like your ActionItemCompletion logic
        records_created = 0
        present_participants = session.participants.filter(
            attendance_status='PRESENT',
            passed=True
        ).select_related('employee', 'session__topic')

        for participant in present_participants:
            # Check if record already exists (prevent duplicates)
            existing = TrainingRecord.objects.filter(
                employee=participant.employee,
                topic=session.topic,
                session=session
            ).exists()

            if not existing:
                TrainingRecord.objects.create(
                    employee=participant.employee,
                    topic=session.topic,
                    session=session,
                    completed_date=session.actual_date,
                    status='ACTIVE',
                    added_manually=False,
                    created_by=self.request.user
                    # valid_until and certificate_number are auto-set in model.save()
                )
                records_created += 1

        # Send certificate issued notifications
        try:
            from apps.notifications.services import NotificationService
            NotificationService.notify(
                content_object=session,
                notification_type='CERTIFICATE_ISSUED',
                module='TRAINING'
            )
        except Exception as e:
            print(f"Completion notification error: {e}")

        messages.success(
            self.request,
            f'Session "{session.session_number}" completed! '
            f'{records_created} certificate(s) auto-generated.'
        )
        return redirect('training:session_detail', pk=session.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['present_participants'] = self.object.participants.filter(
            attendance_status='PRESENT'
        ).select_related('employee')
        return context


# ============================================================
# 6. CANCEL SESSION VIEW
# ============================================================

class CancelSessionView(TrainingAccessMixin, UpdateView):
    """Cancel a training session"""
    model = TrainingSession
    form_class = TrainingSessionCancelForm
    template_name = 'training/session_cancel.html'

    def dispatch(self, request, *args, **kwargs):
        session = get_object_or_404(TrainingSession, pk=kwargs['pk'])
        if session.status in ['COMPLETED', 'CANCELLED']:
            messages.error(request, f"Session is already {session.status.lower()}.")
            return redirect('training:session_detail', pk=session.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        session = form.save(commit=False)
        session.status = 'CANCELLED'
        session.save()

        # Notify participants of cancellation
        try:
            from apps.notifications.services import NotificationService
            NotificationService.notify(
                content_object=session,
                notification_type='SESSION_CANCELLED',
                module='TRAINING'
            )
        except Exception as e:
            print(f"Cancellation notification error: {e}")

        messages.warning(
            self.request,
            f'Session "{session.session_number}" has been cancelled.'
        )
        return redirect('training:session_list')

    def get_success_url(self):
        return reverse_lazy('training:session_list')


# ============================================================
# 7. TRAINING RECORD VIEWS
#    Certificate management
# ============================================================

class TrainingRecordListView(TrainingAccessMixin, ListView):
    """
    List training records / certificates.
    Like IncidentListView with role-based filtering.
    """
    model = TrainingRecord
    template_name = 'training/record_list.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = TrainingRecord.objects.select_related(
            'employee', 'topic', 'session'
        ).order_by('-completed_date')

        # Role-based filtering — same as IncidentListView
        if user.is_superuser or (
            hasattr(user, 'role') and user.role and user.role.name == 'ADMIN'
        ):
            pass
        elif hasattr(user, 'role') and user.role and user.role.name == 'EMPLOYEE':
            queryset = queryset.filter(employee=user)
        elif user.plant:
            queryset = queryset.filter(employee__plant=user.plant)
        else:
            queryset = queryset.filter(employee=user)

        # Filters
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(employee__first_name__icontains=search) |
                Q(employee__last_name__icontains=search) |
                Q(employee__employee_id__icontains=search) |
                Q(certificate_number__icontains=search)
            )

        topic = self.request.GET.get('topic', '')
        if topic:
            queryset = queryset.filter(topic_id=topic)

        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)

        expiry_filter = self.request.GET.get('expiry', '')
        today = timezone.now().date()
        if expiry_filter == '30':
            queryset = queryset.filter(
                valid_until__lte=today + datetime.timedelta(days=30),
                valid_until__gte=today
            )
        elif expiry_filter == '60':
            queryset = queryset.filter(
                valid_until__lte=today + datetime.timedelta(days=60),
                valid_until__gte=today
            )
        elif expiry_filter == 'expired':
            queryset = queryset.filter(valid_until__lt=today)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['topics'] = TrainingTopic.objects.filter(is_active=True).order_by('name')
        context['status_choices'] = TrainingRecord.STATUS_CHOICES
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_topic'] = self.request.GET.get('topic', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_expiry'] = self.request.GET.get('expiry', '')
        return context


class ManualCertificateUploadView(TrainingAccessMixin, CreateView):
    """
    Manually upload certificate for external training.
    Like your IncidentAttachmentForm upload view.
    """
    model = TrainingRecord
    form_class = TrainingRecordManualForm
    template_name = 'training/manual_certificate.html'
    success_url = reverse_lazy('training:record_list')

    def dispatch(self, request, *args, **kwargs):
        if not (
            request.user.is_superuser or
            getattr(request.user, 'can_upload_training_certificate', False) or
            (hasattr(request.user, 'role') and request.user.role and
             request.user.role.name in ['ADMIN', 'SAFETY OFFICER'])
        ):
            messages.error(request, "You don't have permission to upload certificates.")
            return redirect('training:record_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        record = form.save(commit=False)
        record.added_manually = True
        record.status = 'ACTIVE'
        record.created_by = self.request.user
        record.save()

        messages.success(
            self.request,
            f'Certificate "{record.certificate_number}" uploaded successfully!'
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['topics'] = TrainingTopic.objects.filter(is_active=True).order_by('name')
        return context


# ============================================================
# 8. MY TRAININGS VIEW (Employee self-view)
#    Like your MyActionItemsView
# ============================================================

class MyTrainingsView(LoginRequiredMixin, ListView):
    """
    Employee's own training history + upcoming sessions.
    Like your MyActionItemsView.
    """
    model = TrainingRecord
    template_name = 'training/my_trainings.html'
    context_object_name = 'records'
    paginate_by = 15

    def get_queryset(self):
        return TrainingRecord.objects.filter(
            employee=self.request.user
        ).select_related('topic', 'session').order_by('-completed_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()

        # Stats
        all_records = TrainingRecord.objects.filter(employee=user)
        context['total_trainings'] = all_records.count()
        context['active_count'] = all_records.filter(status='ACTIVE').count()
        context['expired_count'] = all_records.filter(
            valid_until__lt=today
        ).count()
        context['expiring_soon_count'] = all_records.filter(
            status='ACTIVE',
            valid_until__lte=today + datetime.timedelta(days=30),
            valid_until__gte=today
        ).count()

        # Upcoming sessions I'm invited to
        context['upcoming_sessions'] = TrainingParticipant.objects.filter(
            employee=user,
            session__status='SCHEDULED',
            session__scheduled_date__gte=today
        ).select_related('session', 'session__topic', 'session__plant').order_by(
            'session__scheduled_date'
        )[:5]

        return context


# ============================================================
# 9. COMPLIANCE VIEW
#    Like your IncidentDashboardView stats section
# ============================================================

class TrainingComplianceView(TrainingAccessMixin, TemplateView):
    """
    Compliance Matrix — who has what training.
    Shows Green/Red/Yellow compliance status per employee.
    """
    template_name = 'training/compliance.html'

    def dispatch(self, request, *args, **kwargs):
        if not (
            request.user.is_superuser or
            getattr(request.user, 'can_view_training_compliance', False) or
            (hasattr(request.user, 'role') and request.user.role and
             request.user.role.name in ['ADMIN', 'SAFETY OFFICER', 'PLANT HEAD', 'HOD'])
        ):
            messages.error(request, "You don't have permission to view compliance reports.")
            return redirect('training:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()

        # Role-based employee filtering
        if user.is_superuser or (
            hasattr(user, 'role') and user.role and user.role.name == 'ADMIN'
        ):
            employees = User.objects.filter(
                is_active=True, is_active_employee=True
            ).select_related('plant', 'department', 'role')
        elif user.plant:
            employees = User.objects.filter(
                is_active=True,
                is_active_employee=True,
                plant=user.plant
            ).select_related('plant', 'department', 'role')
        else:
            employees = User.objects.filter(id=user.id)

        # Filter by plant from URL params
        selected_plant = self.request.GET.get('plant', '')
        if selected_plant and (user.is_superuser or (hasattr(user, 'role') and user.role and user.role.name == 'ADMIN')):
            employees = employees.filter(plant_id=selected_plant)

        # Mandatory topics
        mandatory_topics = TrainingTopic.objects.filter(
            is_mandatory=True, is_active=True
        ).order_by('name')

        # Build compliance matrix
        compliance_matrix = []
        for employee in employees[:50]:  # Limit for performance
            row = {
                'employee': employee,
                'compliance': []
            }
            compliant_count = 0
            for topic in mandatory_topics:
                record = TrainingRecord.objects.filter(
                    employee=employee,
                    topic=topic,
                    status='ACTIVE'
                ).order_by('-completed_date').first()

                if record and record.valid_until >= today:
                    if record.days_until_expiry <= 30:
                        status = 'EXPIRING'    # Yellow
                    else:
                        status = 'COMPLIANT'   # Green
                        compliant_count += 1
                elif record and record.valid_until < today:
                    status = 'EXPIRED'         # Red
                else:
                    status = 'NOT_DONE'        # Grey

                row['compliance'].append({
                    'topic': topic,
                    'status': status,
                    'record': record
                })

            total = mandatory_topics.count()
            row['compliance_percentage'] = round(
                (compliant_count / total * 100), 1
            ) if total > 0 else 0

            compliance_matrix.append(row)

        context['compliance_matrix'] = compliance_matrix
        context['mandatory_topics'] = mandatory_topics
        context['plants'] = Plant.objects.filter(is_active=True)
        context['selected_plant'] = selected_plant
        context['total_employees'] = employees.count()

        return context


# ============================================================
# 10. AJAX VIEWS — like your GetZonesForPlantAjaxView
# ============================================================

class TrainingGetZonesAjaxView(LoginRequiredMixin, TemplateView):
    """AJAX — get zones for plant. Exactly like GetZonesForPlantAjaxView"""

    def get(self, request, *args, **kwargs):
        plant_id = request.GET.get('plant_id')
        zones = Zone.objects.filter(
            plant_id=plant_id, is_active=True
        ).values('id', 'name', 'code')
        return JsonResponse(list(zones), safe=False)


class TrainingGetLocationsAjaxView(LoginRequiredMixin, TemplateView):
    """AJAX — get locations for zone. Exactly like GetLocationsForZoneAjaxView"""

    def get(self, request, *args, **kwargs):
        zone_id = request.GET.get('zone_id')
        locations = Location.objects.filter(
            zone_id=zone_id, is_active=True
        ).values('id', 'name', 'code')
        return JsonResponse(list(locations), safe=False)


class TrainingGetSublocationsAjaxView(LoginRequiredMixin, TemplateView):
    """AJAX — get sublocations for location"""

    def get(self, request, *args, **kwargs):
        location_id = request.GET.get('location_id')
        sublocations = SubLocation.objects.filter(
            location_id=location_id, is_active=True
        ).values('id', 'name', 'code')
        return JsonResponse(list(sublocations), safe=False)


class TrainingGetEmployeesAjaxView(LoginRequiredMixin, TemplateView):
    """
    AJAX — search employees for adding as participants.
    Filtered by plant.
    """

    def get(self, request, *args, **kwargs):
        plant_id = request.GET.get('plant_id', '')
        search = request.GET.get('search', '')
        session_id = request.GET.get('session_id', '')

        employees = User.objects.filter(
            is_active=True,
            is_active_employee=True
        )

        if plant_id:
            employees = employees.filter(
                Q(plant_id=plant_id) | Q(assigned_plants=plant_id)
            ).distinct()

        if search:
            employees = employees.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(employee_id__icontains=search)
            )

        # Exclude already added to session
        if session_id:
            already_added = TrainingParticipant.objects.filter(
                session_id=session_id
            ).values_list('employee_id', flat=True)
            employees = employees.exclude(id__in=already_added)

        data = [
            {
                'id': emp.id,
                'name': emp.get_full_name(),
                'employee_id': emp.employee_id or '',
                'department': emp.department.name if emp.department else '',
                'designation': emp.job_title or ''
            }
            for emp in employees[:30]  # Limit results
        ]
        return JsonResponse(data, safe=False)


# ============================================================
# 11. TRAINING NOTIFICATION VIEWS
#     Exactly like your NotificationListView + MarkNotificationReadView
# ============================================================

class TrainingNotificationListView(LoginRequiredMixin, ListView):
    """List training notifications — like NotificationListView"""
    model = TrainingNotification
    template_name = 'training/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        return TrainingNotification.objects.filter(
            recipient=self.request.user
        ).select_related('session', 'training_record')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unread_count'] = self.get_queryset().filter(is_read=False).count()
        return context


class MarkTrainingNotificationReadView(LoginRequiredMixin, View):
    """Mark training notification as read — like MarkNotificationReadView"""

    def post(self, request, pk):
        notification = get_object_or_404(
            TrainingNotification,
            pk=pk,
            recipient=request.user
        )
        notification.mark_as_read()
        return JsonResponse({'status': 'success'})


class MarkAllTrainingNotificationsReadView(LoginRequiredMixin, View):
    """Mark all training notifications read — like MarkAllNotificationsReadView"""

    def post(self, request):
        TrainingNotification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return JsonResponse({'status': 'success'})