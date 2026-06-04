from django.db.models import Q

from apps.platform.core.domain.policies import PolicyDecision
from apps.platform.core.models import PolicyDefinition


class PolicyEngine:
    def evaluate(self, policy_type, context, tenant=None):
        policies = (
            PolicyDefinition.objects.filter(policy_type=policy_type, is_active=True)
            .filter(Q(tenant=tenant) | Q(tenant__isnull=True))
            .order_by("priority", "-tenant_id")
        )
        effects = {}
        for policy in policies:
            if self._matches(policy.conditions, context):
                effect = policy.effect or {}
                effects.update(effect)
                if effect.get("deny"):
                    return PolicyDecision(False, policy.key, effects)
                if effect.get("require_approval"):
                    return PolicyDecision(False, "approval_required", effects)
        return PolicyDecision(True, "policy_allowed", effects)

    def _matches(self, conditions, context):
        if not conditions:
            return True
        for key, expected in conditions.items():
            actual = context.get(key)
            if isinstance(expected, dict):
                if "lt" in expected and not (actual < expected["lt"]):
                    return False
                if "lte" in expected and not (actual <= expected["lte"]):
                    return False
                if "gt" in expected and not (actual > expected["gt"]):
                    return False
                if "gte" in expected and not (actual >= expected["gte"]):
                    return False
                if "in" in expected and actual not in expected["in"]:
                    return False
            elif actual != expected:
                return False
        return True

