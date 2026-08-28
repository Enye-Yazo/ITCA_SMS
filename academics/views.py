# academics/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Campus, Program, Module, ProgramModule, Class, Enrollment
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