from django import template

from commerce.models import Quotation

register = template.Library()


@register.simple_tag
def quotation_admin_stats():
    """
    Admin dashboard counters (global across owners).
    Kept as a template tag to avoid coupling to AdminSite/index view overrides.
    """
    try:
        total = Quotation.objects.count()
        pending_approval = Quotation.objects.filter(status=Quotation.Status.VERIFIED).count()
        converted = Quotation.objects.filter(status=Quotation.Status.CONVERTED).count()
        rejected = Quotation.objects.filter(status=Quotation.Status.REJECTED).count()
    except Exception:
        total = 0
        pending_approval = 0
        converted = 0
        rejected = 0

    return {
        "total": total,
        "pending_approval": pending_approval,
        "converted": converted,
        "rejected": rejected,
    }

