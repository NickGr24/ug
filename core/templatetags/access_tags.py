"""
Custom template tags for Access Control system.
"""

from django import template
from core.services import AccessControlService

register = template.Library()

_service = AccessControlService()


@register.simple_tag
def is_present(entity_type, entity_id):
    """Check if entity is currently present."""
    return _service.is_entity_present(entity_type, entity_id)


@register.inclusion_tag('core/partials/_status_badge.html')
def status_badge(entity_type, entity_id):
    """Render status badge for entity."""
    is_present = _service.is_entity_present(entity_type, entity_id)
    return {'is_present': is_present}
