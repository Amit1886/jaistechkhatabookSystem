from django.urls import path

from api.gateway.views import (
    EnterpriseCommandGateway,
    EnterpriseJobGateway,
    EnterprisePolicyGateway,
    EnterpriseQueryGateway,
)
from apps.platform.core.observability.health import enterprise_health

urlpatterns = [
    path("commands/", EnterpriseCommandGateway.as_view(), name="enterprise-command-gateway"),
    path("queries/", EnterpriseQueryGateway.as_view(), name="enterprise-query-gateway"),
    path("jobs/", EnterpriseJobGateway.as_view(), name="enterprise-job-gateway"),
    path("policies/evaluate/", EnterprisePolicyGateway.as_view(), name="enterprise-policy-gateway"),
    path("health/", enterprise_health, name="enterprise-health"),
]

