from django import template

register = template.Library()


@register.filter
def has_group(user, group_name):
    """Uso en templates: {% if user|has_group:'Admin' %}...{% endif %}"""
    try:
        return user.is_authenticated and user.groups.filter(name=group_name).exists()
    except Exception:
        return False
