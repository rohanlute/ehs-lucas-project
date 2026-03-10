from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def get_month_value(obj, month):

    if not obj:
        return ""

    field = f"{month}_qty"

    return getattr(obj, field, "")