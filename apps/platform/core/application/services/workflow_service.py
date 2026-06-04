from apps.platform.core.application.services.event_service import EventService
from apps.platform.core.infrastructure.repositories.core_repository import CoreRepository
from apps.platform.identity.application.services.permission_service import PermissionService


class WorkflowError(Exception):
    pass


class WorkflowService:
    def __init__(self, repository=None, permission_service=None, event_service=None):
        self.repository = repository or CoreRepository()
        self.permission_service = permission_service or PermissionService()
        self.event_service = event_service or EventService()

    def transition(self, workflow_key, transition_key, current_state, payload, user, tenant=None):
        workflow = self.repository.workflow_by_key(workflow_key, tenant)
        if not workflow:
            raise WorkflowError("Workflow not found.")
        transition = self.repository.transition_by_key(workflow, transition_key)
        if not transition:
            raise WorkflowError("Transition not found.")
        if transition.from_state != current_state:
            raise WorkflowError("Transition is not allowed from current state.")
        if transition.permission_key and not self.permission_service.has_permission(user, transition.permission_key, tenant=tenant).allowed:
            raise WorkflowError("Permission denied.")
        event_payload = {
            "workflow": workflow.key,
            "transition": transition.key,
            "from_state": transition.from_state,
            "to_state": transition.to_state,
            "payload": payload,
        }
        self.event_service.publish("workflow_transitioned", event_payload, tenant=tenant, user=user)
        for action in transition.actions or []:
            if action.get("event_type"):
                self.event_service.publish(action["event_type"], event_payload, tenant=tenant, user=user)
        return {"state": transition.to_state, "workflow": workflow.key, "transition": transition.key}
