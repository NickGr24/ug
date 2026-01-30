"""
Views for Access Control system.
"""

import csv
import io
import json
from datetime import datetime, timedelta

from django.views.generic import TemplateView, ListView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.db.models import Q, Case, When, Value, IntegerField

from .models import Location, Employee, Vehicle, LogEntry, Department
from .forms import EmployeeForm, VehicleForm, HistoryFilterForm
from .services import AccessControlService


class LocationMixin:
    """Mixin to filter data by user's location permissions."""

    def get_user_location(self):
        """Get current location for filtering."""
        user = self.request.user
        if user.is_admin:
            # Admin can switch locations via session
            location_id = self.request.session.get('current_location_id')
            if location_id:
                return Location.objects.filter(id=location_id, is_active=True).first()
            return None  # Admin sees all if no location selected
        return user.location

    def filter_by_location(self, queryset, location_field='location'):
        """Filter queryset by user's location."""
        location = self.get_user_location()
        if location:
            return queryset.filter(**{location_field: location})
        return queryset


class DashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard with all tabs."""
    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_tab'] = self.request.GET.get('tab', 'registry')
        return context


class SwitchLocationView(LoginRequiredMixin, View):
    """Switch current location (for admin only)."""

    def post(self, request):
        if not request.user.is_admin:
            return HttpResponse(status=403)

        location_id = request.POST.get('location_id')
        if location_id:
            request.session['current_location_id'] = int(location_id)
        else:
            request.session.pop('current_location_id', None)

        # Return HTMX redirect to refresh page
        response = HttpResponse()
        response['HX-Redirect'] = '/'
        return response


class EmployeesTabView(LoginRequiredMixin, LocationMixin, ListView):
    """Employees tab content."""
    template_name = 'core/employees_tab.html'
    context_object_name = 'employees'
    paginate_by = 50

    def get_queryset(self):
        qs = Employee.objects.filter(activ=True).select_related('location', 'department')
        qs = self.filter_by_location(qs)

        # Search filter
        search = self.request.GET.get('search', '')
        if search:
            qs = qs.filter(
                Q(nume__icontains=search) |
                Q(department__name__icontains=search) |
                Q(ext_id__icontains=search)
            )

        # Get present employee IDs and sort by presence (present first)
        service = AccessControlService()
        location = self.get_user_location()
        present = service.get_present_now(location)
        present_ids = [p['entity_id'] for p in present if p['entity_type'] == 'employee']

        if present_ids:
            qs = qs.annotate(
                is_present=Case(
                    When(id__in=present_ids, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ).order_by('-is_present', 'nume')
        else:
            qs = qs.order_by('nume')

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        return context


class EmployeesListPartial(EmployeesTabView):
    """HTMX partial for employees list."""
    template_name = 'core/partials/_employees_list.html'


class VehiclesTabView(LoginRequiredMixin, LocationMixin, ListView):
    """Vehicles tab content."""
    template_name = 'core/vehicles_tab.html'
    context_object_name = 'vehicles'
    paginate_by = 50

    def get_queryset(self):
        qs = Vehicle.objects.filter(activ=True).select_related('location')
        qs = self.filter_by_location(qs)

        # Search filter
        search = self.request.GET.get('search', '')
        if search:
            qs = qs.filter(
                Q(plate_number__icontains=search) |
                Q(descriere__icontains=search) |
                Q(proprietar__icontains=search)
            )

        # Get present vehicle IDs and sort by presence (present first)
        service = AccessControlService()
        location = self.get_user_location()
        present = service.get_present_now(location)
        present_ids = [p['entity_id'] for p in present if p['entity_type'] == 'vehicle']

        if present_ids:
            qs = qs.annotate(
                is_present=Case(
                    When(id__in=present_ids, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ).order_by('-is_present', 'plate_number')
        else:
            qs = qs.order_by('plate_number')

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        return context


class VehiclesListPartial(VehiclesTabView):
    """HTMX partial for vehicles list."""
    template_name = 'core/partials/_vehicles_list.html'


class PresentTabView(LoginRequiredMixin, LocationMixin, TemplateView):
    """Currently present tab."""
    template_name = 'core/present_tab.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        location = self.get_user_location()

        service = AccessControlService()
        present = service.get_present_now(location)

        context['present_employees'] = [p for p in present if p['entity_type'] == 'employee']
        context['present_vehicles'] = [p for p in present if p['entity_type'] == 'vehicle']
        context['total_count'] = len(present)

        return context


class PresentNowPartial(PresentTabView):
    """HTMX partial for present now list."""
    template_name = 'core/partials/_present_now.html'


class HistoryTabView(LoginRequiredMixin, LocationMixin, TemplateView):
    """History tab with filters - shows paired entry/exit records."""
    template_name = 'core/history_tab.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        location = self.get_user_location()

        # Get filter values
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        entity_type = self.request.GET.get('entity_type')

        # Get visit history (paired IN/OUT records)
        service = AccessControlService()
        visits = service.get_visit_history(
            location=location,
            date_from=date_from,
            date_to=date_to,
            entity_type_filter=entity_type,
            limit=500
        )

        context['visits'] = visits
        context['filter_form'] = HistoryFilterForm(self.request.GET)
        context['today'] = timezone.now().date()
        context['yesterday'] = timezone.now().date() - timedelta(days=1)
        context['week_ago'] = timezone.now().date() - timedelta(days=7)
        return context


class RegistryTabView(LoginRequiredMixin, LocationMixin, TemplateView):
    """Combined registry tab with employees and vehicles."""
    template_name = 'core/registry_tab.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        location = self.get_user_location()

        # Get present entities
        service = AccessControlService()
        present = service.get_present_now(location)
        present_emp_ids = [p['entity_id'] for p in present if p['entity_type'] == 'employee']
        present_veh_ids = [p['entity_id'] for p in present if p['entity_type'] == 'vehicle']

        # Get employees sorted by presence
        employees = Employee.objects.filter(activ=True).select_related('location', 'department')
        employees = self.filter_by_location(employees)
        if present_emp_ids:
            employees = employees.annotate(
                is_present=Case(
                    When(id__in=present_emp_ids, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ).order_by('-is_present', 'nume')
        else:
            employees = employees.order_by('nume')

        # Get vehicles sorted by presence
        vehicles = Vehicle.objects.filter(activ=True).select_related('location')
        vehicles = self.filter_by_location(vehicles)
        if present_veh_ids:
            vehicles = vehicles.annotate(
                is_present=Case(
                    When(id__in=present_veh_ids, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ).order_by('-is_present', 'plate_number')
        else:
            vehicles = vehicles.order_by('plate_number')

        context['employees'] = employees[:50]
        context['vehicles'] = vehicles[:50]
        return context


class SettingsTabView(LoginRequiredMixin, TemplateView):
    """Settings tab (admin features)."""
    template_name = 'core/settings_tab.html'


class EmployeeAutocompleteView(LoginRequiredMixin, View):
    """HTMX endpoint for employee name autocomplete."""

    def get(self, request):
        query = request.GET.get('q', '').strip()
        if len(query) < 2:
            return HttpResponse('')

        employees = Employee.objects.filter(
            nume__icontains=query,
            activ=True
        ).values('nume')[:10]

        if not employees:
            return HttpResponse('<div class="p-2 text-muted small">Nu s-au gasit angajati</div>')

        html = '<div class="list-group list-group-flush">'
        for emp in employees:
            html += f'''<button type="button"
                class="list-group-item list-group-item-action py-2"
                onclick="selectProprietar('{emp['nume']}')">{emp['nume']}</button>'''
        html += '</div>'

        return HttpResponse(html)


class EmployeeEntryView(LoginRequiredMixin, LocationMixin, View):
    """HTMX endpoint for recording employee entry/exit."""

    def post(self, request, pk):
        direction = request.POST.get('direction')
        if direction not in ['IN', 'OUT']:
            return HttpResponse(
                '<div class="alert alert-danger">Directie invalida</div>',
                status=400
            )

        employee = get_object_or_404(Employee, pk=pk, activ=True)
        location = self.get_user_location()

        # If admin hasn't selected a location, use the employee's registered location
        if not location and request.user.is_admin:
            location = employee.location

        if not location:
            return HttpResponse(
                '<div class="alert alert-warning">Selectati o locatie intai</div>',
                status=400
            )

        # Check permissions: officer can only mark entry for their location's employees
        # OR for employees currently present at their location (for exit)
        if request.user.is_officer:
            service = AccessControlService()
            if direction == 'IN' and employee.location != location:
                return HttpResponse(
                    '<div class="alert alert-warning">Puteti inregistra intrari doar pentru angajatii locatiei dvs.</div>',
                    status=403
                )
            # For OUT, check if employee is present at this location
            if direction == 'OUT':
                present = service.get_present_now(location)
                present_ids = [p['entity_id'] for p in present if p['entity_type'] == 'employee']
                if employee.id not in present_ids:
                    return HttpResponse(
                        '<div class="alert alert-warning">Angajatul nu este prezent la aceasta locatie.</div>',
                        status=403
                    )

        service = AccessControlService()
        success, message = service.mark_employee_entry(
            employee_id=pk,
            direction=direction,
            location=location,
            recorded_by=request.user
        )

        if success:
            action = 'Intrare' if direction == 'IN' else 'Iesire'
            return HttpResponse(
                f'<div class="alert alert-success alert-dismissible fade show" role="alert">'
                f'{employee.nume}: {action} inregistrata cu succes'
                f'<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
                f'</div>',
                headers={
                    'HX-Trigger': 'refreshPresent, refreshList'
                }
            )
        else:
            return HttpResponse(
                f'<div class="alert alert-warning alert-dismissible fade show" role="alert">'
                f'{message}'
                f'<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
                f'</div>',
                status=200
            )


class VehicleEntryView(LoginRequiredMixin, LocationMixin, View):
    """HTMX endpoint for recording vehicle entry/exit."""

    def post(self, request, pk):
        direction = request.POST.get('direction')
        if direction not in ['IN', 'OUT']:
            return HttpResponse(
                '<div class="alert alert-danger">Directie invalida</div>',
                status=400
            )

        vehicle = get_object_or_404(Vehicle, pk=pk, activ=True)
        location = self.get_user_location()

        # If admin hasn't selected a location, use the vehicle's registered location
        if not location and request.user.is_admin:
            location = vehicle.location

        if not location:
            return HttpResponse(
                '<div class="alert alert-warning">Selectati o locatie intai</div>',
                status=400
            )

        # Check permissions: officer can only mark entry for their location's vehicles
        # OR for vehicles currently present at their location (for exit)
        if request.user.is_officer:
            service = AccessControlService()
            if direction == 'IN' and vehicle.location != location:
                return HttpResponse(
                    '<div class="alert alert-warning">Puteti inregistra intrari doar pentru vehiculele locatiei dvs.</div>',
                    status=403
                )
            if direction == 'OUT':
                present = service.get_present_now(location)
                present_ids = [p['entity_id'] for p in present if p['entity_type'] == 'vehicle']
                if vehicle.id not in present_ids:
                    return HttpResponse(
                        '<div class="alert alert-warning">Vehiculul nu este prezent la aceasta locatie.</div>',
                        status=403
                    )

        service = AccessControlService()
        success, message = service.mark_vehicle_entry(
            vehicle_id=pk,
            direction=direction,
            location=location,
            recorded_by=request.user
        )

        if success:
            action = 'Intrare' if direction == 'IN' else 'Iesire'
            # message contains info about linked employee (if any)
            extra_info = message if message else ''
            return HttpResponse(
                f'<div class="alert alert-success alert-dismissible fade show" role="alert">'
                f'{vehicle.plate_number}: {action} inregistrata cu succes{extra_info}'
                f'<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
                f'</div>',
                headers={
                    'HX-Trigger': 'refreshPresent, refreshList'
                }
            )
        else:
            return HttpResponse(
                f'<div class="alert alert-warning alert-dismissible fade show" role="alert">'
                f'{message}'
                f'<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
                f'</div>',
                status=200
            )


class EmployeeCreateView(LoginRequiredMixin, LocationMixin, CreateView):
    """Create new employee."""
    model = Employee
    form_class = EmployeeForm
    template_name = 'core/partials/_employee_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # For officers, only allow their location
        if self.request.user.is_officer:
            form.fields['location'].queryset = Location.objects.filter(id=self.request.user.location_id)
            form.fields['location'].initial = self.request.user.location
            form.fields['location'].widget.attrs['disabled'] = True
        return form

    def form_valid(self, form):
        # For officers, force their location
        if self.request.user.is_officer:
            form.instance.location = self.request.user.location
        form.save()
        return HttpResponse(
            '<div class="alert alert-success">Angajat adaugat cu succes!</div>',
            headers={'HX-Trigger': json.dumps({'refreshList': None, 'closeModal': None})}
        )

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class EmployeeUpdateView(LoginRequiredMixin, LocationMixin, UpdateView):
    """Edit employee."""
    model = Employee
    form_class = EmployeeForm
    template_name = 'core/partials/_employee_form.html'

    def get_queryset(self):
        qs = Employee.objects.all()
        if self.request.user.is_officer:
            qs = qs.filter(location=self.request.user.location)
        return qs

    def form_valid(self, form):
        form.save()
        return HttpResponse(
            '<div class="alert alert-success">Angajat actualizat cu succes!</div>',
            headers={'HX-Trigger': json.dumps({'refreshList': None, 'closeModal': None})}
        )


class VehicleCreateView(LoginRequiredMixin, LocationMixin, CreateView):
    """Create new vehicle."""
    model = Vehicle
    form_class = VehicleForm
    template_name = 'core/partials/_vehicle_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.is_officer:
            form.fields['location'].queryset = Location.objects.filter(id=self.request.user.location_id)
            form.fields['location'].initial = self.request.user.location
            form.fields['location'].widget.attrs['disabled'] = True
        return form

    def form_valid(self, form):
        if self.request.user.is_officer:
            form.instance.location = self.request.user.location
        form.save()
        return HttpResponse(
            '<div class="alert alert-success">Vehicul adaugat cu succes!</div>',
            headers={'HX-Trigger': json.dumps({'refreshList': None, 'closeModal': None})}
        )


class VehicleUpdateView(LoginRequiredMixin, LocationMixin, UpdateView):
    """Edit vehicle."""
    model = Vehicle
    form_class = VehicleForm
    template_name = 'core/partials/_vehicle_form.html'

    def get_queryset(self):
        qs = Vehicle.objects.all()
        if self.request.user.is_officer:
            qs = qs.filter(location=self.request.user.location)
        return qs

    def form_valid(self, form):
        form.save()
        return HttpResponse(
            '<div class="alert alert-success">Vehicul actualizat cu succes!</div>',
            headers={'HX-Trigger': json.dumps({'refreshList': None, 'closeModal': None})}
        )


class HistoryExportView(LoginRequiredMixin, LocationMixin, View):
    """Export history to CSV - paired entry/exit records."""

    def get(self, request):
        location = self.get_user_location()

        # Get filter values
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        entity_type = request.GET.get('entity_type')

        # Get visit history (paired IN/OUT records)
        service = AccessControlService()
        visits = service.get_visit_history(
            location=location,
            date_from=date_from,
            date_to=date_to,
            entity_type_filter=entity_type,
            limit=10000
        )

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        filename = f"jurnal_{timezone.now().strftime('%d-%m-%Y')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        # Add BOM for Excel compatibility
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow(['Tip', 'Nume/Numar', 'Departament', 'Data Intrare', 'Ora Intrare', 'Data Iesire', 'Ora Iesire', 'Durata', 'Locatie'])

        for visit in visits:
            # Calculate duration
            duration = ''
            if visit['exit_time']:
                delta = visit['exit_time'] - visit['entry_time']
                total_seconds = int(delta.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                duration = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

            writer.writerow([
                'Angajat' if visit['entity_type'] == 'employee' else 'Vehicul',
                visit['entity_name'],
                visit['entity_department'] or '',
                visit['entry_time'].strftime('%d.%m.%Y'),
                visit['entry_time'].strftime('%H:%M'),
                visit['exit_time'].strftime('%d.%m.%Y') if visit['exit_time'] else 'Pe teritoriu',
                visit['exit_time'].strftime('%H:%M') if visit['exit_time'] else '',
                duration,
                visit['entry_location'].name if visit['entry_location'] else ''
            ])

        return response


class EmployeesExportView(LoginRequiredMixin, LocationMixin, View):
    """Export employees to CSV."""

    def get(self, request):
        qs = Employee.objects.filter(activ=True).select_related('location', 'department')
        qs = self.filter_by_location(qs)

        # Search filter
        search = request.GET.get('search', '')
        if search:
            qs = qs.filter(
                Q(nume__icontains=search) |
                Q(department__name__icontains=search) |
                Q(ext_id__icontains=search)
            )

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        filename = f"angajati_{timezone.now().strftime('%d-%m-%Y')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow(['ID', 'Nume', 'Departament', 'Locatie', 'Status'])

        service = AccessControlService()
        for emp in qs:
            is_present = service.is_entity_present('employee', emp.id)
            writer.writerow([
                emp.ext_id or emp.id,
                emp.nume,
                emp.department.name if emp.department else '',
                emp.location.name,
                'Pe teritoriu' if is_present else 'Absent'
            ])

        return response


class VehiclesExportView(LoginRequiredMixin, LocationMixin, View):
    """Export vehicles to CSV."""

    def get(self, request):
        qs = Vehicle.objects.filter(activ=True).select_related('location')
        qs = self.filter_by_location(qs)

        # Search filter
        search = request.GET.get('search', '')
        if search:
            qs = qs.filter(
                Q(plate_number__icontains=search) |
                Q(descriere__icontains=search) |
                Q(proprietar__icontains=search)
            )

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        filename = f"vehicule_{timezone.now().strftime('%d-%m-%Y')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow(['Numar', 'Descriere', 'Proprietar', 'Locatie', 'Status'])

        service = AccessControlService()
        for veh in qs:
            is_present = service.is_entity_present('vehicle', veh.id)
            writer.writerow([
                veh.plate_number,
                veh.descriere or '',
                veh.proprietar or '',
                veh.location.name,
                'Pe teritoriu' if is_present else 'Absent'
            ])

        return response


class PresentExportView(LoginRequiredMixin, LocationMixin, View):
    """Export currently present to CSV."""

    def get(self, request):
        location = self.get_user_location()
        service = AccessControlService()
        present = service.get_present_now(location)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        filename = f"prezenti_{timezone.now().strftime('%d-%m-%Y')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow(['Tip', 'Nume/Numar', 'Departament/Descriere', 'Ora intrare', 'Locatie intrare'])

        for item in present:
            writer.writerow([
                'Angajat' if item['entity_type'] == 'employee' else 'Vehicul',
                item['name'],
                item.get('departament') or item.get('descriere') or '',
                item['entry_time'].strftime('%H:%M') if item['entry_time'] else '',
                item['entry_location'].name if item['entry_location'] else ''
            ])

        return response


class ImportEmployeesView(LoginRequiredMixin, View):
    """Import employees from CSV."""

    def post(self, request):
        if not request.user.is_admin:
            return HttpResponse('Acces interzis', status=403)

        csv_file = request.FILES.get('csv_file')
        location_id = request.POST.get('location_id')

        if not csv_file or not location_id:
            return HttpResponse(
                '<div class="alert alert-danger">Selectati fisierul CSV si locatia.</div>',
                status=400
            )

        try:
            location = Location.objects.get(id=location_id)
        except Location.DoesNotExist:
            return HttpResponse(
                '<div class="alert alert-danger">Locatia nu exista.</div>',
                status=400
            )

        try:
            # Read CSV file
            decoded = csv_file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded), delimiter=';')

            count = 0
            for row in reader:
                # Expected columns: nume, departament, ext_id (optional)
                nume = row.get('nume') or row.get('Nume') or row.get('NUME')
                if not nume:
                    continue

                dept_name = row.get('departament') or row.get('Departament') or row.get('DEPARTAMENT') or ''
                ext_id = row.get('ext_id') or row.get('ID') or row.get('id') or ''

                # Get or create department if specified
                department = None
                if dept_name.strip():
                    department, _ = Department.objects.get_or_create(
                        name=dept_name.strip(),
                        location=location
                    )

                Employee.objects.get_or_create(
                    nume=nume.strip(),
                    location=location,
                    defaults={
                        'department': department,
                        'ext_id': str(ext_id).strip()
                    }
                )
                count += 1

            return HttpResponse(
                f'<div class="alert alert-success">Importati {count} angajati pentru {location.name}.</div>',
                headers={'HX-Trigger': 'refreshList'}
            )
        except Exception as e:
            return HttpResponse(
                f'<div class="alert alert-danger">Eroare la import: {str(e)}</div>',
                status=400
            )


class NavbarLocationPartial(LoginRequiredMixin, TemplateView):
    """HTMX partial for navbar location selector with present counts."""
    template_name = 'core/partials/_navbar_location.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        service = AccessControlService()
        counts = service.get_present_counts_by_location()

        if user.is_admin:
            locations = list(Location.objects.filter(is_active=True))
            # Attach present count to each location
            for loc in locations:
                loc.present_count = counts.get(loc.id, 0)
            context['locations'] = locations
            context['total_present'] = sum(counts.values())

            # Get current location from session
            location_id = self.request.session.get('current_location_id')
            if location_id:
                context['current_location'] = Location.objects.filter(id=location_id).first()
                context['present_counts'] = counts.get(location_id, 0)
            else:
                context['current_location'] = None
        else:
            # Officer sees only their location
            context['current_location'] = user.location
            context['present_counts'] = counts.get(user.location_id, 0) if user.location_id else 0

        return context


class ImportVehiclesView(LoginRequiredMixin, View):
    """Import vehicles from CSV."""

    def post(self, request):
        if not request.user.is_admin:
            return HttpResponse('Acces interzis', status=403)

        csv_file = request.FILES.get('csv_file')
        location_id = request.POST.get('location_id')

        if not csv_file or not location_id:
            return HttpResponse(
                '<div class="alert alert-danger">Selectati fisierul CSV si locatia.</div>',
                status=400
            )

        try:
            location = Location.objects.get(id=location_id)
        except Location.DoesNotExist:
            return HttpResponse(
                '<div class="alert alert-danger">Locatia nu exista.</div>',
                status=400
            )

        try:
            decoded = csv_file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded), delimiter=';')

            count = 0
            for row in reader:
                # Expected columns: plate_number/numar, descriere, proprietar
                plate = row.get('plate_number') or row.get('numar') or row.get('Numar') or row.get('NUMAR')
                if not plate:
                    continue

                descriere = row.get('descriere') or row.get('Descriere') or row.get('DESCRIERE') or ''
                proprietar = row.get('proprietar') or row.get('Proprietar') or row.get('PROPRIETAR') or ''

                Vehicle.objects.get_or_create(
                    plate_number=plate.strip().upper(),
                    location=location,
                    defaults={
                        'descriere': descriere.strip(),
                        'proprietar': proprietar.strip()
                    }
                )
                count += 1

            return HttpResponse(
                f'<div class="alert alert-success">Importate {count} vehicule pentru {location.name}.</div>',
                headers={'HX-Trigger': 'refreshList'}
            )
        except Exception as e:
            return HttpResponse(
                f'<div class="alert alert-danger">Eroare la import: {str(e)}</div>',
                status=400
            )
