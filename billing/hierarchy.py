from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple


# NOTE:
# - This file is intentionally dependency-light so it can be imported from apps
#   without creating circular imports.
# - String values must stay stable because they are stored on the User model.


BILLING_ACCESS_LEVEL_ADMIN = "admin"
BILLING_ACCESS_LEVEL_USER = "user"

BILLING_ROLE_SUB_USER = "sub_user"
BILLING_ROLE_SUPPLIER = "supplier"
BILLING_ROLE_VENDOR = "vendor"
BILLING_ROLE_CUSTOMER = "customer"
BILLING_ROLE_FIELD_AGENT = "field_agent"
BILLING_ROLE_AI_AGENT = "ai_agent"


def billing_hierarchy_config() -> Dict[str, Any]:
    """
    Configuration source-of-truth for the Billing Model Hierarchy UI.

    This mirrors the shared image reference (Admin -> User -> 6 role types with children).
    """
    return {
        "access_levels": [
            {
                "key": BILLING_ACCESS_LEVEL_ADMIN,
                "label": "Admin",
                "summary": "Full system access (Super Admin)",
                "capabilities": [
                    "Full system access",
                    "Manage all users & roles",
                    "Manage organizations / tenants",
                    "System configuration & settings",
                    "Billing plans, pricing & subscriptions",
                    "Reports & analytics (global)",
                    "Data backup & restore",
                    "Security, permissions & audit logs",
                    "Integrations (APIs, gateways, apps)",
                    "AI agent configuration (global)",
                    "Workflow & approval settings",
                    "Notifications / email / SMS templates",
                    "Manage master data (currencies, taxes, units, etc.)",
                ],
            },
            {
                "key": BILLING_ACCESS_LEVEL_USER,
                "label": "User",
                "summary": "Organization-level user (can manage sub users)",
                "capabilities": [
                    "Manage organization profile",
                    "Manage sub users & assign roles",
                    "View & manage billing",
                    "View reports (organization level)",
                    "Manage modules & feature access",
                    "Manage branches / locations",
                    "Manage API keys (limited)",
                    "User activity & audit logs (limited)",
                    "Set permissions for sub users",
                    "Subscription usage & limits",
                ],
            },
        ],
        "roles": {
            BILLING_ROLE_SUB_USER: {
                "key": BILLING_ROLE_SUB_USER,
                "label": "Sub User",
                "summary": "General users under the organization (role-based access).",
                "assignable_by": "user_or_admin",
                "key_capabilities": [
                    "Access assigned modules",
                    "Create / view / edit assigned data",
                    "Perform transactions",
                    "Generate reports",
                    "Limited settings as per role",
                ],
                "children": [
                    {"key": "team_member", "label": "Team Member"},
                    {"key": "operator", "label": "Operator"},
                    {"key": "data_entry", "label": "Data Entry"},
                    {"key": "viewer", "label": "Viewer"},
                    {"key": "support_staff", "label": "Support Staff"},
                ],
                "permissions": [
                    "Create / Edit / View / Delete",
                    "Approve / Reject (if allowed)",
                    "Export / Print (if allowed)",
                ],
                "data_access": [
                    "Only assigned data",
                    "Own data or team data",
                    "No access to other org data",
                ],
            },
            BILLING_ROLE_SUPPLIER: {
                "key": BILLING_ROLE_SUPPLIER,
                "label": "Supplier",
                "summary": "Suppliers provide products/services to the organization.",
                "assignable_by": "user_or_admin",
                "key_capabilities": [
                    "Manage products / services",
                    "Manage stock / inventory",
                    "Create invoices / bills",
                    "View payments & receivables",
                    "Offers & discounts",
                    "Delivery / challan management",
                    "Reports (supplier level)",
                ],
                "children": [
                    {"key": "sales_executive", "label": "Sales Executive"},
                    {"key": "stock_manager", "label": "Stock Manager"},
                    {"key": "accountant", "label": "Accountant"},
                    {"key": "purchase_manager", "label": "Purchase Manager"},
                    {"key": "delivery_manager", "label": "Delivery Manager"},
                    {"key": "support_staff", "label": "Support Staff"},
                ],
                "permissions": [
                    "Manage products & stock",
                    "Create & manage invoices",
                    "View payments",
                    "Manage deliveries",
                    "Access reports",
                ],
                "data_access": [
                    "Supplier's own data only",
                    "No access to other suppliers",
                    "Branch-wise access",
                ],
            },
            BILLING_ROLE_VENDOR: {
                "key": BILLING_ROLE_VENDOR,
                "label": "Vendor",
                "summary": "Vendors sell products/services to customers via the system.",
                "assignable_by": "user_or_admin",
                "key_capabilities": [
                    "Manage products / services",
                    "Manage orders",
                    "Create invoices",
                    "Manage payments",
                    "Offers & discounts",
                    "Returns / refunds",
                    "Reports (vendor level)",
                ],
                "children": [
                    {"key": "shop_manager", "label": "Shop Manager"},
                    {"key": "sales_staff", "label": "Sales Staff"},
                    {"key": "accountant", "label": "Accountant"},
                    {"key": "inventory_manager", "label": "Inventory Manager"},
                    {"key": "customer_support", "label": "Customer Support"},
                    {"key": "logistics_manager", "label": "Logistics Manager"},
                ],
                "permissions": [
                    "Manage products",
                    "Manage orders",
                    "Create invoices",
                    "Manage payments",
                    "View reports",
                ],
                "data_access": [
                    "Vendor's own data only",
                    "No access to other vendors",
                    "Branch-wise access",
                ],
            },
            BILLING_ROLE_CUSTOMER: {
                "key": BILLING_ROLE_CUSTOMER,
                "label": "Customer",
                "summary": "Customers buy products/services from vendors.",
                "assignable_by": "user_or_admin",
                "key_capabilities": [
                    "Browse products / services",
                    "Place orders",
                    "View invoices",
                    "Make payments",
                    "Track orders",
                    "Raise support tickets",
                    "Wallet / balance (if any)",
                    "Reports (customer level)",
                ],
                "children": [
                    {"key": "family_member", "label": "Family Member"},
                    {"key": "authorized_user", "label": "Authorized User"},
                    {"key": "billing_contact", "label": "Billing Contact"},
                    {"key": "support_contact", "label": "Support Contact"},
                ],
                "permissions": [
                    "Place orders",
                    "View invoices",
                    "Make payments",
                    "Raise tickets",
                    "View statements",
                ],
                "data_access": [
                    "Customer's own data only",
                    "No access to other customers",
                    "Account-based access",
                ],
            },
            BILLING_ROLE_FIELD_AGENT: {
                "key": BILLING_ROLE_FIELD_AGENT,
                "label": "Field Agent",
                "summary": "Field agents collect data/payments and perform field ops.",
                "assignable_by": "user_or_admin",
                "key_capabilities": [
                    "Visit & check-in / check-out",
                    "Collect data (forms, surveys)",
                    "Create orders / leads",
                    "Collect payments (POS)",
                    "Generate bills / receipts",
                    "Capture photos / signatures",
                    "Submit reports / activities",
                    "View route / locations",
                ],
                "children": [
                    {"key": "team_leader", "label": "Team Leader"},
                    {"key": "field_executive", "label": "Field Executive"},
                    {"key": "collection_agent", "label": "Collection Agent"},
                    {"key": "survey_executive", "label": "Survey Executive"},
                    {"key": "support_staff", "label": "Support Staff"},
                ],
                "permissions": [
                    "Access assigned tasks",
                    "Collect data",
                    "Create orders",
                    "Collect payments",
                    "Submit reports",
                    "View schedules",
                ],
                "data_access": [
                    "Only assigned area / route",
                    "No access to other areas",
                    "Own submitted data",
                ],
            },
            BILLING_ROLE_AI_AGENT: {
                "key": BILLING_ROLE_AI_AGENT,
                "label": "AI Agent",
                "summary": "AI-powered intelligent agent for automation and insights.",
                "assignable_by": "admin_only",
                "key_capabilities": [
                    "Automation workflows",
                    "Data analysis & insights",
                    "Smart recommendations",
                    "Predictive analytics",
                    "Auto response / chat",
                    "Anomaly detection",
                    "Report generation (AI)",
                    "Learning & optimization",
                ],
                "children": [
                    {"key": "chatbot_agent", "label": "Chatbot Agent"},
                    {"key": "analytics_agent", "label": "Analytics Agent"},
                    {"key": "automation_agent", "label": "Automation Agent"},
                    {"key": "recommendation_agent", "label": "Recommendation Agent"},
                    {"key": "notification_agent", "label": "Notification Agent"},
                    {"key": "data_mining_agent", "label": "Data Mining Agent"},
                ],
                "permissions": [
                    "Run automations",
                    "Analyze data",
                    "Generate insights",
                    "Auto respond",
                    "Learn & optimize",
                ],
                "data_access": [
                    "As per AI configuration",
                    "Train on allowed data only",
                    "No manual data edit",
                ],
            },
        },
    }


def get_role_label(role_type: str) -> str:
    cfg = billing_hierarchy_config()
    role = (cfg.get("roles") or {}).get(role_type) or {}
    return str(role.get("label") or role_type or "")


def get_child_label(role_type: str, child_role: str) -> str:
    cfg = billing_hierarchy_config()
    role = (cfg.get("roles") or {}).get(role_type) or {}
    for item in role.get("children") or []:
        if (item.get("key") or "") == child_role:
            return str(item.get("label") or child_role or "")
    return str(child_role or "")


def role_children(role_type: str) -> List[Dict[str, str]]:
    cfg = billing_hierarchy_config()
    role = (cfg.get("roles") or {}).get(role_type) or {}
    children = role.get("children") or []
    out: List[Dict[str, str]] = []
    for item in children:
        k = str(item.get("key") or "").strip()
        if not k:
            continue
        out.append({"key": k, "label": str(item.get("label") or k)})
    return out


# --- Minimal RBAC bridge (stores defaults into User.permissions_json) ---

_ACCESS_LEVEL_DEFAULTS: Dict[str, Set[str]] = {
    BILLING_ACCESS_LEVEL_ADMIN: {
        "billing.admin.full_access",
        "billing.admin.manage_users",
        "billing.admin.manage_roles",
        "billing.admin.manage_tenants",
        "billing.admin.manage_plans",
        "billing.admin.audit_logs",
        "billing.admin.integrations",
        "billing.admin.backup_restore",
    },
    BILLING_ACCESS_LEVEL_USER: {
        "billing.user.manage_org",
        "billing.user.manage_subusers",
        "billing.user.manage_billing",
        "billing.user.view_reports",
        "billing.user.manage_modules",
        "billing.user.manage_locations",
        "billing.user.manage_api_keys",
    },
}

_ROLE_DEFAULTS: Dict[str, Set[str]] = {
    BILLING_ROLE_SUB_USER: {"billing.role.sub_user"},
    BILLING_ROLE_SUPPLIER: {"billing.role.supplier", "feature:portal.supplier"},
    BILLING_ROLE_VENDOR: {"billing.role.vendor"},
    BILLING_ROLE_CUSTOMER: {"billing.role.customer", "feature:portal.customer"},
    BILLING_ROLE_FIELD_AGENT: {"billing.role.field_agent", "feature:field.agents"},
    BILLING_ROLE_AI_AGENT: {"billing.role.ai_agent", "feature:advanced.ai_reports"},
}


def default_permission_keys(
    *,
    access_level: str = "",
    role_type: str = "",
    child_role: str = "",
) -> Set[str]:
    keys: Set[str] = set()
    if access_level in _ACCESS_LEVEL_DEFAULTS:
        keys |= set(_ACCESS_LEVEL_DEFAULTS[access_level])
    if role_type in _ROLE_DEFAULTS:
        keys |= set(_ROLE_DEFAULTS[role_type])
    if role_type and child_role:
        keys.add(f"billing.child.{role_type}.{child_role}")
    return keys


def apply_billing_defaults_to_user(user, *, overwrite: bool = False) -> Tuple[int, int]:
    """
    Write default billing keys to `user.permissions_json`.

    Returns: (created_keys, updated_keys)
    """
    if not user:
        return (0, 0)

    blob = getattr(user, "permissions_json", None) or {}
    if not isinstance(blob, dict):
        blob = {}

    access_level = str(getattr(user, "billing_access_level", "") or "").strip()
    role_type = str(getattr(user, "billing_role_type", "") or "").strip()
    child_role = str(getattr(user, "billing_child_role", "") or "").strip()

    created = 0
    updated = 0
    for key in sorted(default_permission_keys(access_level=access_level, role_type=role_type, child_role=child_role)):
        if key not in blob:
            blob[key] = True
            created += 1
        elif overwrite and blob.get(key) is not True:
            blob[key] = True
            updated += 1

    user.permissions_json = blob
    return (created, updated)

