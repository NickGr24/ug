"""
Django Admin configuration for Access Control system.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Location, User, Department, Employee, Vehicle, LogEntry


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'role', 'location', 'is_active', 'is_staff']
    list_filter = ['role', 'location', 'is_active', 'is_staff']
    search_fields = ['username', 'email', 'first_name', 'last_name']

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Control Acces', {'fields': ('role', 'location')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Control Acces', {'fields': ('role', 'location')}),
    )


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'is_active', 'created_at']
    list_filter = ['location', 'is_active']
    search_fields = ['name']
    list_editable = ['is_active']
    ordering = ['location', 'name']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['ext_id', 'nume', 'department', 'location', 'activ', 'created_at']
    list_filter = ['location', 'department', 'activ']
    search_fields = ['nume', 'ext_id']
    list_editable = ['activ']
    ordering = ['nume']
    readonly_fields = ['ext_id', 'created_at', 'updated_at']
    autocomplete_fields = ['department']


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['plate_number', 'descriere', 'proprietar', 'location', 'activ', 'created_at']
    list_filter = ['location', 'activ']
    search_fields = ['plate_number', 'descriere', 'proprietar']
    list_editable = ['activ']
    ordering = ['plate_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'location', 'entity_type', 'entity_name', 'direction', 'recorded_by']
    list_filter = ['location', 'entity_type', 'direction', 'timestamp']
    search_fields = ['entity_id']
    date_hierarchy = 'timestamp'
    readonly_fields = ['timestamp', 'recorded_by', 'entity_type', 'entity_id', 'direction', 'location']
    ordering = ['-timestamp']

    def has_add_permission(self, request):
        return False  # Log entries should only be created through the app

    def has_change_permission(self, request, obj=None):
        return False  # Log entries should not be editable

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superuser can delete


# Customize admin site
admin.site.site_header = 'Control Acces - Administrare'
admin.site.site_title = 'Control Acces'
admin.site.index_title = 'Panou de administrare'
