"""
Models for the Access Control system.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class Location(models.Model):
    """
    Represents physical locations/checkpoints.
    Three locations: UG Asachi, UG Sf.Vineri, UG Centrul de Excelenta Ungheni
    """
    name = models.CharField(max_length=100, unique=True, verbose_name='Nume')
    code = models.CharField(max_length=20, unique=True, verbose_name='Cod')
    address = models.TextField(blank=True, verbose_name='Adresa')
    is_active = models.BooleanField(default=True, verbose_name='Activ')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Locatie'
        verbose_name_plural = 'Locatii'

    def __str__(self):
        return self.name


class User(AbstractUser):
    """
    Custom user model with role and location assignment.
    """
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Administrator'
        OFFICER = 'officer', 'Ofiter de Serviciu'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.OFFICER,
        verbose_name='Rol'
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='officers',
        verbose_name='Locatie',
        help_text='Locatia asignata pentru Ofiteri de Serviciu. Gol pentru Administratori.'
    )

    class Meta:
        ordering = ['username']
        verbose_name = 'Utilizator'
        verbose_name_plural = 'Utilizatori'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_officer(self):
        return self.role == self.Role.OFFICER and not self.is_superuser


class Department(models.Model):
    """
    Department within a location.
    """
    name = models.CharField(max_length=100, verbose_name='Nume')
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='departments',
        verbose_name='Locatie'
    )
    is_active = models.BooleanField(default=True, verbose_name='Activ')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Departament'
        verbose_name_plural = 'Departamente'
        constraints = [
            models.UniqueConstraint(
                fields=['location', 'name'],
                name='unique_department_per_location'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.location.code})"


class Employee(models.Model):
    """
    Employee registered at a specific location.
    """
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='employees',
        verbose_name='Locatie',
        help_text='Locatia unde este inregistrat angajatul'
    )
    ext_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='ID Extern',
        help_text='ID extern (ex. din sistemul HR)'
    )
    nume = models.CharField(max_length=200, verbose_name='Nume')
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        verbose_name='Departament'
    )
    activ = models.BooleanField(default=True, verbose_name='Activ')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nume']
        verbose_name = 'Angajat'
        verbose_name_plural = 'Angajati'
        indexes = [
            models.Index(fields=['nume']),
            models.Index(fields=['location', 'activ']),
        ]

    def __str__(self):
        return f"{self.nume} ({self.location.code})"

    def save(self, *args, **kwargs):
        # Auto-generate ext_id if not provided
        if not self.ext_id and not self.pk:
            # Get count for this location
            count = Employee.objects.filter(location=self.location).count()
            self.ext_id = f"EMP{self.location.code[:3].upper()}{count + 1:04d}"
        super().save(*args, **kwargs)


class Vehicle(models.Model):
    """
    Vehicle registered at a specific location.
    """
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='vehicles',
        verbose_name='Locatie',
        help_text='Locatia unde este inregistrat vehiculul'
    )
    plate_number = models.CharField(
        max_length=20,
        verbose_name='Numar inmatriculare'
    )
    descriere = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Descriere'
    )
    proprietar = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Proprietar'
    )
    activ = models.BooleanField(default=True, verbose_name='Activ')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['plate_number']
        verbose_name = 'Vehicul'
        verbose_name_plural = 'Vehicule'
        # Plate number unique per location
        constraints = [
            models.UniqueConstraint(
                fields=['location', 'plate_number'],
                name='unique_vehicle_plate_per_location'
            )
        ]
        indexes = [
            models.Index(fields=['plate_number']),
            models.Index(fields=['location', 'activ']),
        ]

    def __str__(self):
        return f"{self.plate_number} ({self.location.code})"


class LogEntry(models.Model):
    """
    Records entry/exit events.
    Location field indicates WHERE the entry/exit occurred.
    """
    class EntityType(models.TextChoices):
        EMPLOYEE = 'employee', 'Angajat'
        VEHICLE = 'vehicle', 'Vehicul'

    class Direction(models.TextChoices):
        IN = 'IN', 'Intrare'
        OUT = 'OUT', 'Iesire'

    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='log_entries',
        verbose_name='Locatie',
        help_text='Locatia unde a avut loc evenimentul'
    )
    entity_type = models.CharField(
        max_length=10,
        choices=EntityType.choices,
        verbose_name='Tip entitate'
    )
    entity_id = models.PositiveIntegerField(verbose_name='ID Entitate')
    direction = models.CharField(
        max_length=3,
        choices=Direction.choices,
        verbose_name='Directie'
    )
    timestamp = models.DateTimeField(default=timezone.now, verbose_name='Data si ora')
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_entries',
        verbose_name='Inregistrat de'
    )

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Inregistrare jurnal'
        verbose_name_plural = 'Inregistrari jurnal'
        indexes = [
            models.Index(fields=['entity_type', 'entity_id', '-timestamp']),
            models.Index(fields=['location', '-timestamp']),
            models.Index(fields=['direction', '-timestamp']),
            models.Index(fields=['-timestamp']),
        ]

    def __str__(self):
        return f"{self.get_entity_type_display()} {self.entity_id} - {self.get_direction_display()} @ {self.location.code}"

    @property
    def entity(self):
        """Get the actual entity (Employee or Vehicle)."""
        if self.entity_type == self.EntityType.EMPLOYEE:
            return Employee.objects.filter(id=self.entity_id).first()
        return Vehicle.objects.filter(id=self.entity_id).first()

    @property
    def entity_name(self):
        """Get entity display name."""
        entity = self.entity
        if entity:
            if self.entity_type == self.EntityType.EMPLOYEE:
                return entity.nume
            return entity.plate_number
        return f"[Sters {self.entity_type} #{self.entity_id}]"

    @property
    def entity_department(self):
        """Get entity department (for employees only)."""
        if self.entity_type == self.EntityType.EMPLOYEE:
            entity = self.entity
            if entity and entity.department:
                return entity.department.name
            return ''
        return ''
