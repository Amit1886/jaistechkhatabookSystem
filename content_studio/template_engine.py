from django.conf import settings
from django.utils import timezone


def format_code(code: str) -> str:
    return code.strip()


def render_template(template_name: str, context: dict) -> str:
    from django.template.loader import render_to_string
    return render_to_string(template_name, context)
