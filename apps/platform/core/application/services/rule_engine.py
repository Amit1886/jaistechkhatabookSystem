from django.db.models import Q

from apps.platform.core.models import RuleDefinition


class RuleEngine:
    def evaluate(self, rule_type, context, tenant=None):
        rules = (
            RuleDefinition.objects.filter(rule_type=rule_type, is_active=True)
            .filter(Q(tenant=tenant) | Q(tenant__isnull=True))
            .order_by("priority", "-tenant_id")
        )
        actions = []
        for rule in rules:
            if self._matches(rule.when, context):
                actions.append({"rule": rule.key, "then": rule.then})
        return actions

    def _matches(self, when, context):
        if not when:
            return True
        for key, expected in when.items():
            actual = context.get(key)
            if isinstance(expected, dict):
                if "lt" in expected and not (actual < expected["lt"]):
                    return False
                if "gt" in expected and not (actual > expected["gt"]):
                    return False
                if "eq" in expected and actual != expected["eq"]:
                    return False
            elif actual != expected:
                return False
        return True

