"""
Management command to seed initial data.
Creates locations, admin user, and officer users.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Location, Department, Employee, Vehicle

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed initial data: locations, users, and sample employees/vehicles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Also create sample employees and vehicles'
        )

    def handle(self, *args, **options):
        self.stdout.write('Seeding data...')

        # Create locations
        locations_data = [
            {'name': 'UG Asachi', 'code': 'ASACHI'},
            {'name': 'UG Sf.Vineri', 'code': 'SFVINERI'},
            {'name': 'UG Centrul de Excelenta Ungheni', 'code': 'UNGHENI'},
        ]

        locations = {}
        for loc_data in locations_data:
            loc, created = Location.objects.get_or_create(
                code=loc_data['code'],
                defaults={'name': loc_data['name']}
            )
            locations[loc_data['code']] = loc
            if created:
                self.stdout.write(f'  Created location: {loc.name}')
            else:
                self.stdout.write(f'  Location exists: {loc.name}')

        # Create superuser (admin)
        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123',
                first_name='Administrator',
                last_name='Sistema',
                role='admin'
            )
            self.stdout.write(self.style.SUCCESS(f'  Created admin user: admin / admin123'))
        else:
            self.stdout.write('  Admin user already exists')

        # Create officer users
        officers_data = [
            {'username': 'ofiter_asachi', 'first_name': 'Ofiter', 'last_name': 'Asachi', 'location': 'ASACHI'},
            {'username': 'ofiter_sfvineri', 'first_name': 'Ofiter', 'last_name': 'Sf.Vineri', 'location': 'SFVINERI'},
            {'username': 'ofiter_ungheni', 'first_name': 'Ofiter', 'last_name': 'Ungheni', 'location': 'UNGHENI'},
        ]

        for officer_data in officers_data:
            if not User.objects.filter(username=officer_data['username']).exists():
                user = User.objects.create_user(
                    username=officer_data['username'],
                    password='officer123',
                    first_name=officer_data['first_name'],
                    last_name=officer_data['last_name'],
                    role='officer',
                    location=locations[officer_data['location']]
                )
                self.stdout.write(self.style.SUCCESS(
                    f'  Created officer: {officer_data["username"]} / officer123 ({officer_data["location"]})'
                ))
            else:
                self.stdout.write(f'  Officer {officer_data["username"]} already exists')

        # Create sample employees and vehicles if --full flag is provided
        if options['full']:
            self.stdout.write('\nCreating sample employees and vehicles...')

            employees_data = [
                # ASACHI
                {'nume': 'Ion Popescu', 'department_name': 'Paza', 'location': 'ASACHI'},
                {'nume': 'Maria Ionescu', 'department_name': 'IT', 'location': 'ASACHI'},
                {'nume': 'Alexandru Stan', 'department_name': 'Administrativ', 'location': 'ASACHI'},
                # SFVINERI
                {'nume': 'Elena Rusu', 'department_name': 'Paza', 'location': 'SFVINERI'},
                {'nume': 'Andrei Munteanu', 'department_name': 'Tehnic', 'location': 'SFVINERI'},
                {'nume': 'Vasile Cojocaru', 'department_name': 'Administrativ', 'location': 'SFVINERI'},
                # UNGHENI
                {'nume': 'Ana Chirila', 'department_name': 'Paza', 'location': 'UNGHENI'},
                {'nume': 'Mihai Lungu', 'department_name': 'IT', 'location': 'UNGHENI'},
                {'nume': 'Cristina Moraru', 'department_name': 'Administrativ', 'location': 'UNGHENI'},
            ]

            for emp_data in employees_data:
                location = locations[emp_data['location']]
                # Get or create department for this location
                department, dept_created = Department.objects.get_or_create(
                    name=emp_data['department_name'],
                    location=location
                )
                if dept_created:
                    self.stdout.write(f'  Created department: {department.name} ({location.code})')

                emp, created = Employee.objects.get_or_create(
                    nume=emp_data['nume'],
                    location=location,
                    defaults={'department': department}
                )
                if created:
                    self.stdout.write(f'  Created employee: {emp.nume}')

            vehicles_data = [
                # ASACHI
                {'plate_number': 'ABC 123', 'descriere': 'Autoturism', 'proprietar': 'Ion Popescu', 'location': 'ASACHI'},
                {'plate_number': 'DEF 456', 'descriere': 'Utilitara', 'proprietar': 'Firma', 'location': 'ASACHI'},
                # SFVINERI
                {'plate_number': 'GHI 789', 'descriere': 'Autoturism', 'proprietar': 'Elena Rusu', 'location': 'SFVINERI'},
                {'plate_number': 'JKL 012', 'descriere': 'Camion', 'proprietar': 'Transport SRL', 'location': 'SFVINERI'},
                # UNGHENI
                {'plate_number': 'MNO 345', 'descriere': 'Autoturism', 'proprietar': 'Mihai Lungu', 'location': 'UNGHENI'},
                {'plate_number': 'PQR 678', 'descriere': 'Microbuz', 'proprietar': 'Firma', 'location': 'UNGHENI'},
            ]

            for veh_data in vehicles_data:
                veh, created = Vehicle.objects.get_or_create(
                    plate_number=veh_data['plate_number'],
                    location=locations[veh_data['location']],
                    defaults={
                        'descriere': veh_data['descriere'],
                        'proprietar': veh_data['proprietar']
                    }
                )
                if created:
                    self.stdout.write(f'  Created vehicle: {veh.plate_number}')

        self.stdout.write(self.style.SUCCESS('\nSeeding completed!'))
        self.stdout.write('\nCredentials:')
        self.stdout.write('  Admin: admin / admin123')
        self.stdout.write('  Officers: ofiter_asachi, ofiter_sfvineri, ofiter_ungheni / officer123')
