from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from hierarchy.models import AgentCustomerAssignment


@transaction.atomic
def assign_customer_to_agent(
    *,
    company,
    customer,
    agent,
    assigned_by=None,
    reason: str = "",
    metadata: dict | None = None,
) -> AgentCustomerAssignment:
    """
    Create/replace active assignment for a customer.

    This function preserves history by closing the previous active assignment.
    """

    active = (
        AgentCustomerAssignment.objects.select_for_update()
        .filter(company=company, customer=customer, unassigned_at__isnull=True)
        .order_by("-assigned_at", "-id")
        .first()
    )
    if active and active.agent_id == agent.id:
        return active
    if active:
        active.unassigned_at = timezone.now()
        active.save(update_fields=["unassigned_at"])

    return AgentCustomerAssignment.objects.create(
        company=company,
        customer=customer,
        agent=agent,
        assigned_by=assigned_by,
        reason=(reason or "")[:200],
        metadata=metadata or {},
    )


def get_active_agent_for_customer(*, company, customer):
    return (
        AgentCustomerAssignment.objects.filter(company=company, customer=customer, unassigned_at__isnull=True)
        .select_related("agent")
        .order_by("-assigned_at", "-id")
        .first()
    )

