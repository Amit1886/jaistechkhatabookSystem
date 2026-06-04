export const MODULE_UI_STANDARD = {
  shell: "EnterpriseTopbar + DynamicSidebar + TabbedWorkspace",
  workflow: "Draft -> Review -> Approval -> Completed -> Cancelled",
  forms: "DynamicFormBuilder or shared Input/Button/Card primitives",
  tables: "DataTable with FilterBar and WorkflowBadge",
  notifications: "NotificationCenter and toast registry",
  search: "Global command palette and useGlobalSearch",
  dashboards: "DashboardBuilder and widgetRegistry",
  approvals: "ApprovalCard with centralized workflow states",
};

export const MODULES = [
  "pos",
  "inventory",
  "billing",
  "crm",
  "accounting",
  "manufacturing",
  "distribution",
  "analytics",
  "reports",
  "admin",
];

export function standardForModule(moduleKey) {
  return {
    module: moduleKey,
    ...MODULE_UI_STANDARD,
  };
}

