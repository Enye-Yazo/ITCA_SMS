# academics/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import ProtectedError, Q

from .models import Campus, Program, Module, ProgramModule, Class, Enrollment, AttendanceRecord
from .forms import (
    CampusForm, ProgramForm, ModuleForm,
    ClassForm, ProgramModuleForm
)


def exec_only(view_func):
    """
    Decorator that restricts a view to Exec Admins only.
    Redirects all other roles to the dashboard.
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_exec_admin:
            messages.error(request, "Only Exec Admins can access Settings.")
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ─── Settings Index ───────────────────────────────────────────────────────────
@login_required
@exec_only
def settings_index(request):
    """
    Main settings page.
    Displays all campuses, programs, modules, program-module links
    and classes in a tabbed layout.
    """
    module_q = request.GET.get('module_q', '').strip()
    modules = Module.objects.all().order_by('module_name')
    if module_q:
        modules = modules.filter(
            Q(module_name__icontains=module_q) | Q(module_code__icontains=module_q)
        )

    context = {
        'campuses':        Campus.objects.all().order_by('campus_name'),
        'programs':        Program.objects.all().order_by('program_name'),
        'modules':         modules,
        'module_q':        module_q,
        'program_modules': ProgramModule.objects.select_related(
                               'program', 'module'
                           ).order_by('program', 'module'),
        'classes':         Class.objects.select_related(
                               'program', 'campus', 'trainer'
                           ).order_by('-academic_year', 'program'),

        # Forms for inline add panels
        'campus_form':         CampusForm(),
        'program_form':        ProgramForm(),
        'module_form':         ModuleForm(),
        'program_module_form': ProgramModuleForm(),
        'class_form':          ClassForm(),

        # Active tab — preserved after form submission errors
        'active_tab': request.GET.get('tab', 'campuses'),

        'tabs': [
            ('campuses',       'Campuses'),
            ('programs',       'Programs'),
            ('modules',        'Modules'),
            ('classes',        'Classes'),
        ],
    }
    return render(request, 'academics/settings.html', context)


# ─── Campus Views ─────────────────────────────────────────────────────────────
@login_required
@exec_only
def campus_add(request):
    if request.method == 'POST':
        form = CampusForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Campus added successfully.")
            return redirect('academics:settings')
        # Return to settings with the form errors and correct tab open
        context = _settings_context(campus_form=form)
        return render(request, 'academics/settings.html', context)
    return redirect('academics:settings')


@login_required
@exec_only
def campus_edit(request, pk):
    campus = get_object_or_404(Campus, pk=pk)
    if request.method == 'POST':
        form = CampusForm(request.POST, instance=campus)
        if form.is_valid():
            form.save()
            messages.success(request, f"{campus.campus_name} updated.")
            return redirect('academics:settings')
    return redirect('academics:settings')


@login_required
@exec_only
def campus_delete(request, pk):
    campus = get_object_or_404(Campus, pk=pk)
    if request.method == 'POST':
        name = campus.campus_name
        try:
            campus.delete()
            messages.success(request, f"{name} deleted.")
        except ProtectedError:
            messages.error(
                request,
                f"Can't delete {name} — it's still referenced by classes, applicants, "
                f"or staff. Deactivate it instead, or reassign those first."
            )
    return redirect(f"{reverse('academics:settings')}?tab=campuses")


# ─── Program Views ────────────────────────────────────────────────────────────
@login_required
@exec_only
def program_add(request):
    if request.method == 'POST':
        form = ProgramForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Program added successfully.")
            return redirect('academics:settings')
        context = _settings_context(program_form=form, active_tab='programs')
        return render(request, 'academics/settings.html', context)
    return redirect('academics:settings')


@login_required
@exec_only
def program_edit(request, pk):
    program = get_object_or_404(Program, pk=pk)
    if request.method == 'POST':
        form = ProgramForm(request.POST, instance=program)
        if form.is_valid():
            form.save()
            messages.success(request, f"{program.program_name} updated.")
            return redirect('academics:settings')
    return redirect('academics:settings')


@login_required
@exec_only
def program_delete(request, pk):
    program = get_object_or_404(Program, pk=pk)
    if request.method == 'POST':
        name = program.program_name
        try:
            program.delete()
            messages.success(request, f"{name} deleted.")
        except ProtectedError:
            messages.error(
                request,
                f"Can't delete {name} — it's still referenced by classes or applicants. "
                f"Deactivate it instead, or reassign those first."
            )
    return redirect(f"{reverse('academics:settings')}?tab=programs")


# ─── Module Views ─────────────────────────────────────────────────────────────
@login_required
@exec_only
def module_add(request):
    if request.method == 'POST':
        form = ModuleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Module added successfully.")
            return redirect('academics:settings')
        context = _settings_context(module_form=form, active_tab='modules')
        return render(request, 'academics/settings.html', context)
    return redirect('academics:settings')


@login_required
@exec_only
def module_edit(request, pk):
    module = get_object_or_404(Module, pk=pk)
    if request.method == 'POST':
        form = ModuleForm(request.POST, instance=module)
        if form.is_valid():
            form.save()
            messages.success(request, f"{module.module_name} updated.")
            return redirect('academics:settings')
    return redirect('academics:settings')


@login_required
@exec_only
def module_delete(request, pk):
    module = get_object_or_404(Module, pk=pk)
    if request.method == 'POST':
        name = module.module_name
        try:
            module.delete()
            messages.success(request, f"{name} deleted.")
        except ProtectedError:
            messages.error(
                request,
                f"Can't delete {name} — students are already assigned to it. "
                f"Deactivate it instead, or unassign it from those students first."
            )
    return redirect(f"{reverse('academics:settings')}?tab=modules")


# ─── Program Module Views ─────────────────────────────────────────────────────
@login_required
@exec_only
def program_module_add(request):
    if request.method == 'POST':
        form = ProgramModuleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Module linked to program.")
            return redirect('academics:settings')
        context = _settings_context(
            program_module_form=form,
            active_tab='program_modules'
        )
        return render(request, 'academics/settings.html', context)
    return redirect('academics:settings')


@login_required
@exec_only
def program_module_delete(request, pk):
    pm = get_object_or_404(ProgramModule, pk=pk)
    if request.method == 'POST':
        pm.delete()
        messages.success(request, "Module unlinked from program.")
    return redirect('academics:settings')


# ─── Class Views ──────────────────────────────────────────────────────────────
@login_required
@exec_only
def class_add(request):
    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Class created successfully.")
            return redirect('academics:settings')
        context = _settings_context(class_form=form, active_tab='classes')
        return render(request, 'academics/settings.html', context)
    return redirect('academics:settings')


@login_required
@exec_only
def class_edit(request, pk):
    class_obj = get_object_or_404(Class, pk=pk)
    if request.method == 'POST':
        form = ClassForm(request.POST, instance=class_obj)
        if form.is_valid():
            form.save()
            messages.success(request, f"Class updated.")
            return redirect('academics:settings')
    return redirect('academics:settings')


@login_required
@exec_only
def class_delete(request, pk):
    class_obj = get_object_or_404(Class, pk=pk)
    if request.method == 'POST':
        name = str(class_obj)
        try:
            class_obj.delete()
            messages.success(request, f"{name} deleted.")
        except ProtectedError:
            messages.error(
                request,
                f"Can't delete {name} — it still has students enrolled. "
                f"Deactivate it instead, or move those students to another class first."
            )
    return redirect(f"{reverse('academics:settings')}?tab=classes")


# ─── Helper ───────────────────────────────────────────────────────────────────
def _settings_context(**overrides):
    """
    Builds the full settings context.
    Accepts overrides so a form with errors can be passed back
    to the correct tab without losing the rest of the page data.
    """
    context = {
        'campuses':        Campus.objects.all().order_by('campus_name'),
        'programs':        Program.objects.all().order_by('program_name'),
        'modules':         Module.objects.all().order_by('module_name'),
        'program_modules': ProgramModule.objects.select_related(
                               'program', 'module'
                           ).order_by('program', 'module'),
        'classes':         Class.objects.select_related(
                               'program', 'campus', 'trainer'
                           ).order_by('-academic_year', 'program'),
        'campus_form':         CampusForm(),
        'program_form':        ProgramForm(),
        'module_form':         ModuleForm(),
        'program_module_form': ProgramModuleForm(),
        'class_form':          ClassForm(),
        'active_tab':          'campuses',

        'tabs': [
            ('campuses',       'Campuses'),
            ('programs',       'Programs'),
            ('modules',        'Modules'),
            ('classes',        'Classes'),
        ],
    }
    context.update(overrides)
    return context

# ─── Attendance ───────────────────────────────────────────────────────────────
def trainer_only(view_func):
    """Restricts a view to Trainers only."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_trainer:
            messages.error(request, "Only Trainers can access Attendance.")
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


@login_required
@trainer_only
def attendance_view(request):
    """
    Daily attendance register for the trainer's own active class.
    A row is auto-created (defaulting to Present) for every actively
    enrolled student the first time that date is opened, so the trainer
    only has to change the exceptions (Late/Absent) rather than mark
    everyone by hand every day.
    """
    from datetime import date as date_cls
    from admissions.models import Student

    classes = Class.objects.filter(trainer=request.user, is_active=True)
    class_id = request.GET.get('class_id') or request.POST.get('class_id')
    selected_class = classes.filter(pk=class_id).first() if class_id else classes.first()

    date_str = request.GET.get('date') or request.POST.get('date')
    try:
        selected_date = date_cls.fromisoformat(date_str) if date_str else date_cls.today()
    except ValueError:
        selected_date = date_cls.today()

    if request.method == 'POST' and selected_class:
        for enrollment in selected_class.enrollments.filter(status=Enrollment.EnrollmentStatus.ACTIVE):
            student = enrollment.student
            status = request.POST.get(f'status_{student.id}', AttendanceRecord.Status.PRESENT)
            time_in = request.POST.get(f'time_in_{student.id}') or None
            notes = request.POST.get(f'notes_{student.id}', '')
            AttendanceRecord.objects.update_or_create(
                student=student, date=selected_date,
                defaults={
                    'class_group': selected_class,
                    'recorded_by': request.user,
                    'status': status,
                    'time_in': time_in,
                    'notes': notes,
                }
            )
        messages.success(request, f"Attendance saved for {selected_date}.")
        return redirect(f"{request.path}?class_id={selected_class.id}&date={selected_date}")

    rows = []
    if selected_class:
        enrollments = selected_class.enrollments.filter(
            status=Enrollment.EnrollmentStatus.ACTIVE
        ).select_related('student', 'student__applicant')

        for enrollment in enrollments:
            student = enrollment.student
            record, _ = AttendanceRecord.objects.get_or_create(
                student=student, date=selected_date,
                defaults={'class_group': selected_class, 'recorded_by': request.user}
            )
            month_records = AttendanceRecord.objects.filter(
                student=student, date__year=selected_date.year, date__month=selected_date.month
            )
            total = month_records.count()
            present = month_records.exclude(status=AttendanceRecord.Status.ABSENT).count()
            mtd_rate = round((present / total) * 100) if total else 100

            rows.append({'student': student, 'record': record, 'mtd_rate': mtd_rate})

    present_count = sum(1 for r in rows if r['record'].status == AttendanceRecord.Status.PRESENT)
    late_count = sum(1 for r in rows if r['record'].status == AttendanceRecord.Status.LATE)
    absent_count = sum(1 for r in rows if r['record'].status == AttendanceRecord.Status.ABSENT)

    context = {
        'classes': classes,
        'selected_class': selected_class,
        'selected_date': selected_date,
        'rows': rows,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'status_choices': AttendanceRecord.Status.choices,
    }
    return render(request, 'academics/attendance.html', context)
