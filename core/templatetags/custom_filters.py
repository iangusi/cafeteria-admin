from django import template
from datetime import timedelta

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Obtiene un item de un diccionario usando una clave"""
    return dictionary.get(key)

@register.filter
def add_days(value, days):
    try:
        return value + timedelta(days=int(days))
    except:
        return value