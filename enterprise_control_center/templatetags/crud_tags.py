from django import template

register = template.Library()


@register.filter
def get_field(obj, field_name):
    try:
        return getattr(obj, field_name)
    except AttributeError:
        return ""


@register.filter
def get_attr(obj, attr_name):
    try:
        return getattr(obj, attr_name)
    except AttributeError:
        return ""


@register.filter
def get_item(obj, key):
    try:
        return obj[key]
    except (TypeError, KeyError, IndexError):
        return ""


@register.filter
def split(value, delimiter):
    if value is None:
        return []
    return value.split(delimiter)


@register.simple_tag
def define(val=None):
    return val
