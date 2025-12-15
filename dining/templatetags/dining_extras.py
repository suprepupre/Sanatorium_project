from django import template

register = template.Library()

@register.filter
def split(value, delimiter):
    """Разделяет строку по разделителю"""
    if not value:
        return []
    return [item.strip() for item in value.split(delimiter) if item.strip()]

@register.filter
def get_item(mapping, key):
    """Позволяет в шаблоне писать d.by_meal|get_item:"breakfast"."""
    if mapping is None:
        return ""
    return mapping.get(key, 0)