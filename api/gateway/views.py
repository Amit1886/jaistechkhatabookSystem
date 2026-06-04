from rest_framework import permissions, serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.platform.core.application.commands.command_bus import CommandBus
from apps.platform.core.application.jobs.job_engine import BackgroundJobEngine
from apps.platform.core.application.queries.query_bus import QueryBus
from apps.platform.core.application.services.policy_engine import PolicyEngine
from apps.platform.core.domain.commands import Command
from apps.platform.core.domain.queries import Query


class CommandSerializer(serializers.Serializer):
    command_type = serializers.CharField(max_length=180)
    payload = serializers.DictField(default=dict)
    idempotency_key = serializers.CharField(max_length=180, required=False, allow_blank=True)


class QuerySerializer(serializers.Serializer):
    query_key = serializers.CharField(max_length=180)
    filters = serializers.DictField(default=dict)


class JobSerializer(serializers.Serializer):
    job_key = serializers.CharField(max_length=180)
    payload = serializers.DictField(default=dict)
    countdown = serializers.IntegerField(required=False, min_value=0)


class PolicySerializer(serializers.Serializer):
    policy_type = serializers.CharField(max_length=40)
    context = serializers.DictField(default=dict)


class EnterpriseCommandGateway(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CommandSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = getattr(request, "identity_tenant", None)
        envelope = CommandBus().dispatch(
            Command(
                command_type=serializer.validated_data["command_type"],
                payload=serializer.validated_data["payload"],
                tenant_id=str(tenant.id) if tenant else None,
                actor_id=str(request.user.id),
                idempotency_key=serializer.validated_data.get("idempotency_key", ""),
            )
        )
        return Response({"command_id": str(envelope.id), "status": envelope.status, "result": envelope.result})


class EnterpriseQueryGateway(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = QuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = getattr(request, "identity_tenant", None)
        result = QueryBus().execute(
            Query(
                query_key=serializer.validated_data["query_key"],
                filters=serializer.validated_data["filters"],
                tenant_id=str(tenant.id) if tenant else None,
                actor_id=str(request.user.id),
            ),
            user=request.user,
        )
        return Response(result)


class EnterpriseJobGateway(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = JobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = BackgroundJobEngine().enqueue(
            serializer.validated_data["job_key"],
            payload=serializer.validated_data["payload"],
            tenant=getattr(request, "identity_tenant", None),
            countdown=serializer.validated_data.get("countdown"),
        )
        status_code = status.HTTP_202_ACCEPTED if result.get("queued") else status.HTTP_404_NOT_FOUND
        return Response(result, status=status_code)


class EnterprisePolicyGateway(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = PolicyEngine().evaluate(
            serializer.validated_data["policy_type"],
            serializer.validated_data["context"],
            tenant=getattr(request, "identity_tenant", None),
        )
        return Response({"allowed": decision.allowed, "reason": decision.reason, "effects": decision.effects})

