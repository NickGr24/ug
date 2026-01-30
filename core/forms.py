"""
Django forms for Access Control system.
"""

from django import forms
from .models import Employee, Vehicle, Department


class EmployeeForm(forms.ModelForm):
    """Form for creating/editing employees."""

    class Meta:
        model = Employee
        fields = ['nume', 'department', 'location', 'activ']
        widgets = {
            'nume': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Introduceti numele complet'
            }),
            'department': forms.Select(attrs={
                'class': 'form-select'
            }),
            'location': forms.Select(attrs={
                'class': 'form-select'
            }),
            'activ': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter departments by location if location is set
        if self.instance and self.instance.location_id:
            self.fields['department'].queryset = Department.objects.filter(
                location=self.instance.location,
                is_active=True
            )
        else:
            self.fields['department'].queryset = Department.objects.filter(is_active=True)

    def clean_nume(self):
        """Validate that employee name is unique."""
        nume = self.cleaned_data.get('nume')
        if not nume:
            return nume

        # Check for existing employee with the same name (case-insensitive)
        qs = Employee.objects.filter(nume__iexact=nume.strip()).select_related('department', 'location')

        # If editing, exclude current instance from check
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            existing = qs.first()
            dept_info = f" ({existing.department.name})" if existing.department else ""
            loc_info = f" - {existing.location.code}" if existing.location else ""
            raise forms.ValidationError(
                f'Un angajat cu numele "{existing.nume}"{dept_info}{loc_info} exista deja.'
            )

        return nume.strip()


class VehicleForm(forms.ModelForm):
    """Form for creating/editing vehicles."""

    class Meta:
        model = Vehicle
        fields = ['plate_number', 'descriere', 'proprietar', 'location', 'activ']
        widgets = {
            'plate_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: ABC 123'
            }),
            'descriere': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Autoturism, Utilitara'
            }),
            'proprietar': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numele proprietarului'
            }),
            'location': forms.Select(attrs={
                'class': 'form-select'
            }),
            'activ': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def clean_plate_number(self):
        """Validate plate number format and uniqueness."""
        import re

        plate_number = self.cleaned_data.get('plate_number')
        if not plate_number:
            return plate_number

        # Normalize plate number (uppercase, strip whitespace)
        plate_number = plate_number.strip().upper()

        # Validate format: only letters, numbers, and spaces allowed
        # Must contain at least one letter and one number
        if not re.match(r'^[A-Z0-9 ]+$', plate_number):
            raise forms.ValidationError(
                'Formatul numarului este invalid. Folositi doar litere, cifre si spatii. Exemplu: ABC 123'
            )

        # Check that it has both letters and numbers
        has_letters = bool(re.search(r'[A-Z]', plate_number))
        has_numbers = bool(re.search(r'[0-9]', plate_number))

        if not has_letters or not has_numbers:
            raise forms.ValidationError(
                'Numarul trebuie sa contina atat litere cat si cifre. Exemplu: ABC 123'
            )

        # Check for existing vehicle with the same plate number (case-insensitive)
        qs = Vehicle.objects.filter(plate_number__iexact=plate_number)

        # If editing, exclude current instance from check
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError(
                f'Un vehicul cu numarul "{plate_number}" exista deja.'
            )

        return plate_number


class HistoryFilterForm(forms.Form):
    """Form for filtering history."""

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='De la'
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Pana la'
    )
    entity_type = forms.ChoiceField(
        required=False,
        choices=[('', 'Toate'), ('employee', 'Angajat'), ('vehicle', 'Vehicul')],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Tip'
    )
    direction = forms.ChoiceField(
        required=False,
        choices=[('', 'Toate'), ('IN', 'Intrare'), ('OUT', 'Iesire')],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Directie'
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Cauta dupa nume/numar...'
        }),
        label='Cautare'
    )
