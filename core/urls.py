"""
URL configuration for core app.
"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Dashboard (main page with tabs)
    path('', views.DashboardView.as_view(), name='dashboard'),

    # Location switching (for admin)
    path('switch-location/', views.SwitchLocationView.as_view(), name='switch_location'),

    # Tab content (for HTMX loading)
    path('tab/registry/', views.RegistryTabView.as_view(), name='registry_tab'),
    path('tab/employees/', views.EmployeesTabView.as_view(), name='employees_tab'),
    path('tab/vehicles/', views.VehiclesTabView.as_view(), name='vehicles_tab'),
    path('tab/present/', views.PresentTabView.as_view(), name='present_tab'),
    path('tab/history/', views.HistoryTabView.as_view(), name='history_tab'),
    path('tab/settings/', views.SettingsTabView.as_view(), name='settings_tab'),

    # HTMX Partial endpoints
    path('htmx/employees-list/', views.EmployeesListPartial.as_view(), name='htmx_employees_list'),
    path('htmx/vehicles-list/', views.VehiclesListPartial.as_view(), name='htmx_vehicles_list'),
    path('htmx/present-now/', views.PresentNowPartial.as_view(), name='htmx_present_now'),
    path('htmx/navbar-location/', views.NavbarLocationPartial.as_view(), name='htmx_navbar_location'),
    path('htmx/employee-autocomplete/', views.EmployeeAutocompleteView.as_view(), name='htmx_employee_autocomplete'),

    # Entry/Exit Actions (HTMX POST endpoints)
    path('htmx/employee/<int:pk>/entry/', views.EmployeeEntryView.as_view(), name='htmx_employee_entry'),
    path('htmx/vehicle/<int:pk>/entry/', views.VehicleEntryView.as_view(), name='htmx_vehicle_entry'),

    # Employee CRUD
    path('employees/add/', views.EmployeeCreateView.as_view(), name='employee_add'),
    path('employees/<int:pk>/edit/', views.EmployeeUpdateView.as_view(), name='employee_edit'),

    # Vehicle CRUD
    path('vehicles/add/', views.VehicleCreateView.as_view(), name='vehicle_add'),
    path('vehicles/<int:pk>/edit/', views.VehicleUpdateView.as_view(), name='vehicle_edit'),

    # CSV Export
    path('history/export/', views.HistoryExportView.as_view(), name='history_export'),
    path('employees/export/', views.EmployeesExportView.as_view(), name='employees_export'),
    path('vehicles/export/', views.VehiclesExportView.as_view(), name='vehicles_export'),
    path('present/export/', views.PresentExportView.as_view(), name='present_export'),

    # CSV Import
    path('employees/import/', views.ImportEmployeesView.as_view(), name='employees_import'),
    path('vehicles/import/', views.ImportVehiclesView.as_view(), name='vehicles_import'),
]
