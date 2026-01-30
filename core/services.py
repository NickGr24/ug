"""
Business logic for Access Control operations.
"""

from typing import Tuple, Optional, List, Dict
from django.db import connection
from django.utils import timezone

from .models import Employee, Vehicle, LogEntry, Location, User


class AccessControlService:
    """
    Business logic for access control operations.
    Handles entry/exit validation and tracking.
    """

    def get_last_direction(self, entity_type: str, entity_id: int) -> Optional[str]:
        """
        Get last direction for an entity (globally, not per location).
        This prevents double entry even across locations.
        """
        last_entry = LogEntry.objects.filter(
            entity_type=entity_type,
            entity_id=entity_id
        ).order_by('-timestamp').first()
        return last_entry.direction if last_entry else None

    def mark_employee_entry(
        self,
        employee_id: int,
        direction: str,
        location: Location,
        recorded_by: User
    ) -> Tuple[bool, Optional[str]]:
        """
        Mark employee entry/exit at a specific location.

        Returns:
            Tuple of (success, error_message)
        """
        try:
            employee = Employee.objects.filter(id=employee_id, activ=True).first()
            if not employee:
                return False, "Angajatul nu a fost gasit sau nu este activ"

            # Check if person is already on territory (prevent double entry)
            last_direction = self.get_last_direction("employee", employee_id)

            if direction == "IN" and last_direction == "IN":
                return False, f"{employee.nume} este deja pe teritoriu. Nu se poate inregistra intrarea de doua ori."

            if direction == "OUT" and last_direction != "IN":
                return False, f"{employee.nume} nu este pe teritoriu. Nu se poate inregistra iesirea fara intrare."

            # Record the entry
            LogEntry.objects.create(
                location=location,
                entity_type=LogEntry.EntityType.EMPLOYEE,
                entity_id=employee_id,
                direction=direction,
                recorded_by=recorded_by
            )

            return True, None

        except Exception as e:
            return False, str(e)

    def mark_vehicle_entry(
        self,
        vehicle_id: int,
        direction: str,
        location: Location,
        recorded_by: User
    ) -> Tuple[bool, Optional[str]]:
        """
        Mark vehicle entry/exit at a specific location.
        If vehicle owner is an employee, also marks their entry/exit.

        Returns:
            Tuple of (success, message) - message contains info about auto-linked employee
        """
        try:
            vehicle = Vehicle.objects.filter(id=vehicle_id, activ=True).first()
            if not vehicle:
                return False, "Vehiculul nu a fost gasit sau nu este activ"

            # Check if vehicle is already on territory
            last_direction = self.get_last_direction("vehicle", vehicle_id)

            if direction == "IN" and last_direction == "IN":
                return False, f"Vehiculul {vehicle.plate_number} este deja pe teritoriu."

            if direction == "OUT" and last_direction != "IN":
                return False, f"Vehiculul {vehicle.plate_number} nu este pe teritoriu."

            # Record the vehicle entry
            LogEntry.objects.create(
                location=location,
                entity_type=LogEntry.EntityType.VEHICLE,
                entity_id=vehicle_id,
                direction=direction,
                recorded_by=recorded_by
            )

            # Check if vehicle owner is an employee and auto-mark their entry/exit
            linked_employee_msg = None
            if vehicle.proprietar:
                employee = Employee.objects.filter(
                    nume__iexact=vehicle.proprietar.strip(),
                    activ=True
                ).first()

                if employee:
                    emp_last_direction = self.get_last_direction("employee", employee.id)

                    # Only auto-mark if employee state needs to change
                    should_mark = False
                    if direction == "IN" and emp_last_direction != "IN":
                        should_mark = True
                    elif direction == "OUT" and emp_last_direction == "IN":
                        should_mark = True

                    if should_mark:
                        LogEntry.objects.create(
                            location=location,
                            entity_type=LogEntry.EntityType.EMPLOYEE,
                            entity_id=employee.id,
                            direction=direction,
                            recorded_by=recorded_by
                        )
                        action = "intrare" if direction == "IN" else "iesire"
                        linked_employee_msg = f" + {employee.nume} ({action} automata)"

            return True, linked_employee_msg

        except Exception as e:
            return False, str(e)

    def get_present_now(self, location: Optional[Location] = None) -> List[Dict]:
        """
        Get all entities currently present at a location.
        If location is None (admin view), returns all present entities.

        Returns list of dicts with entity info.
        """
        # Using raw SQL with CTE for efficiency
        # This finds all entities whose last log entry was 'IN'
        sql = '''
            WITH last_events AS (
                SELECT
                    entity_type,
                    entity_id,
                    direction,
                    timestamp,
                    location_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY entity_type, entity_id
                        ORDER BY timestamp DESC
                    ) as rn
                FROM core_logentry
                {where_clause}
            )
            SELECT
                le.entity_type,
                le.entity_id,
                le.timestamp,
                le.location_id
            FROM last_events le
            WHERE le.rn = 1 AND le.direction = 'IN'
            ORDER BY le.timestamp DESC
        '''

        params = []
        if location:
            where_clause = "WHERE location_id = %s"
            params.append(location.id)
        else:
            where_clause = ""

        sql = sql.format(where_clause=where_clause)

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        # Fetch entity details
        employee_ids = [r[1] for r in rows if r[0] == 'employee']
        vehicle_ids = [r[1] for r in rows if r[0] == 'vehicle']

        employees = {e.id: e for e in Employee.objects.filter(id__in=employee_ids).select_related('location', 'department')}
        vehicles = {v.id: v for v in Vehicle.objects.filter(id__in=vehicle_ids).select_related('location')}
        locations = {loc.id: loc for loc in Location.objects.all()}

        result = []
        for entity_type, entity_id, timestamp, location_id in rows:
            if entity_type == 'employee' and entity_id in employees:
                emp = employees[entity_id]
                result.append({
                    'entity_type': 'employee',
                    'entity_id': entity_id,
                    'name': emp.nume,
                    'departament': emp.department.name if emp.department else '',
                    'entry_time': timestamp,
                    'entry_location': locations.get(location_id),
                    'registered_location': emp.location,
                    'entity': emp
                })
            elif entity_type == 'vehicle' and entity_id in vehicles:
                veh = vehicles[entity_id]
                result.append({
                    'entity_type': 'vehicle',
                    'entity_id': entity_id,
                    'name': veh.plate_number,
                    'descriere': veh.descriere,
                    'proprietar': veh.proprietar,
                    'entry_time': timestamp,
                    'entry_location': locations.get(location_id),
                    'registered_location': veh.location,
                    'entity': veh
                })

        return result

    def get_present_employees_at_location(self, location: Location) -> List[Dict]:
        """Get only employees currently present at a specific location."""
        present = self.get_present_now(location)
        return [p for p in present if p['entity_type'] == 'employee']

    def get_present_vehicles_at_location(self, location: Location) -> List[Dict]:
        """Get only vehicles currently present at a specific location."""
        present = self.get_present_now(location)
        return [p for p in present if p['entity_type'] == 'vehicle']

    def is_entity_present(self, entity_type: str, entity_id: int) -> bool:
        """Check if an entity is currently present (anywhere)."""
        last_direction = self.get_last_direction(entity_type, entity_id)
        return last_direction == 'IN'

    def get_present_counts_by_location(self, employees_only: bool = True) -> Dict[int, int]:
        """
        Get count of currently present entities per location.
        Returns a dict mapping location_id to count.

        Args:
            employees_only: If True, count only employees (default). If False, count all entities.
        """
        entity_filter = "AND entity_type = 'employee'" if employees_only else ""

        sql = f'''
            WITH last_events AS (
                SELECT
                    entity_type,
                    entity_id,
                    direction,
                    location_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY entity_type, entity_id
                        ORDER BY timestamp DESC
                    ) as rn
                FROM core_logentry
                WHERE 1=1 {entity_filter}
            )
            SELECT
                le.location_id,
                COUNT(*) as present_count
            FROM last_events le
            WHERE le.rn = 1 AND le.direction = 'IN'
            GROUP BY le.location_id
        '''

        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()

        return {location_id: count for location_id, count in rows}

    def get_visit_history(
        self,
        location: Optional[Location] = None,
        date_from=None,
        date_to=None,
        entity_type_filter: Optional[str] = None,
        limit: int = 500
    ) -> List[Dict]:
        """
        Get visit history as paired IN/OUT records.
        Returns list of dicts with entry_time, exit_time for each visit.
        If entity is still present (no OUT), exit_time is None.
        """
        # Build filters
        filters = {}
        if location:
            filters['location'] = location
        if date_from:
            filters['timestamp__date__gte'] = date_from
        if date_to:
            filters['timestamp__date__lte'] = date_to
        if entity_type_filter:
            filters['entity_type'] = entity_type_filter

        # Get all entries ordered by entity and timestamp
        entries = LogEntry.objects.filter(**filters).select_related(
            'location', 'recorded_by'
        ).order_by('entity_type', 'entity_id', 'timestamp')

        # Group entries by entity
        from collections import defaultdict
        entity_entries = defaultdict(list)
        for entry in entries:
            key = (entry.entity_type, entry.entity_id)
            entity_entries[key].append(entry)

        # Pair IN/OUT entries
        visits = []
        for (etype, eid), elist in entity_entries.items():
            current_entry = None
            for entry in elist:
                if entry.direction == 'IN':
                    # Start new visit
                    current_entry = entry
                elif entry.direction == 'OUT' and current_entry:
                    # Complete the visit
                    visits.append({
                        'entity_type': etype,
                        'entity_id': eid,
                        'entry_time': current_entry.timestamp,
                        'exit_time': entry.timestamp,
                        'entry_location': current_entry.location,
                        'exit_location': entry.location,
                        'recorded_by_entry': current_entry.recorded_by,
                        'recorded_by_exit': entry.recorded_by,
                        'entity_name': current_entry.entity_name,
                        'entity_department': current_entry.entity_department,
                    })
                    current_entry = None

            # If still present (IN without OUT)
            if current_entry:
                visits.append({
                    'entity_type': etype,
                    'entity_id': eid,
                    'entry_time': current_entry.timestamp,
                    'exit_time': None,  # Still present
                    'entry_location': current_entry.location,
                    'exit_location': None,
                    'recorded_by_entry': current_entry.recorded_by,
                    'recorded_by_exit': None,
                    'entity_name': current_entry.entity_name,
                    'entity_department': current_entry.entity_department,
                })

        # Sort by entry time descending (most recent first)
        visits.sort(key=lambda x: x['entry_time'], reverse=True)

        return visits[:limit]
