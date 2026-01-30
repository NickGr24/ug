"""
Context processors for global template variables.
"""

from django.utils import timezone
from .models import Location


def global_context(request):
    """Add global context variables to all templates."""
    context = {
        'current_time': timezone.now(),
    }

    if request.user.is_authenticated:
        if request.user.is_admin:
            context['locations'] = Location.objects.filter(is_active=True)
            # Get current location from session for admin
            location_id = request.session.get('current_location_id')
            if location_id:
                context['current_location'] = Location.objects.filter(id=location_id).first()
            else:
                context['current_location'] = None
        else:
            # Officer sees only their location
            context['current_location'] = request.user.location
            context['locations'] = []

    return context
