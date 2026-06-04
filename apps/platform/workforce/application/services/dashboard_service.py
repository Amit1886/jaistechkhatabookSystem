from apps.platform.workforce.infrastructure.repositories.workforce_repository import WorkforceRepository


class WorkforceDashboardService:
    def __init__(self, repository=None):
        self.repository = repository or WorkforceRepository()

    def dashboard(self, tenant):
        return self.repository.dashboard(tenant)

    def org_tree(self, tenant):
        return self.repository.org_tree(tenant)

