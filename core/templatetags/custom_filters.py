"""
Custom template filters for the Access Control system.
"""

from django import template

register = template.Library()


@register.filter
def duration_until(start_time, end_time):
    """
    Calculate duration between two datetimes and format it nicely.
    Usage: {{ start_time|duration_until:end_time }}
    """
    if not start_time or not end_time:
        return "-"

    delta = end_time - start_time
    total_seconds = int(delta.total_seconds())

    if total_seconds < 0:
        return "-"

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return f"{seconds}s"
