# 📚 Quick Reference - Plan Permissions API

## Common Operations

### Get User's Plan
```python
from khataapp.models import UserProfile

user_profile = UserProfile.objects.get(user=request.user)
user_plan = user_profile.plan
```

### Check if User Can Do Action
```python
# In views or elsewhere
user_profile = UserProfile.objects.get(user=request.user)
user_plan = user_profile.plan
permissions = user_plan.get_permissions()

if permissions.allow_add_party:
    # Allow user to add party
else:
    raise PermissionDenied("Your plan doesn't allow adding parties")
```

### Get Permission Count
```python
permissions = user_plan.get_permissions()
max_parties = permissions.max_parties

# Check if user exceeded limit
existing_parties = Party.objects.filter(user=request.user).count()
if existing_parties >= max_parties:
    messages.warning(request, f"You've reached the {max_parties} party limit for your plan")
```

### Check All Permissions for a Plan
```python
from billing.models import PlanPermissions

plan_permissions = PlanPermissions.objects.get(plan=plan)

# Access individual permissions
dashboard = plan_permissions.allow_dashboard
commerce = plan_permissions.allow_commerce
max_parties = plan_permissions.max_parties
```

### Enable/Disable Feature for Plan
```python
from billing.models import Plan, PlanPermissions

plan = Plan.objects.get(name="Professional")
permissions = plan.get_permissions()  # Auto-creates if doesn't exist

# Disable exports for free plan
permissions.allow_pdf_export = False
permissions.allow_excel_export = False
permissions.save()
```

## Permission Fields Reference

### Dashboard & Reports
- `allow_dashboard` - Access to dashboard page
- `allow_reports` - Generate reports
- `allow_pdf_export` - Export to PDF
- `allow_excel_export` - Export to Excel
- `allow_analytics` - View analytics

### Party Management
- `allow_add_party` - Create new parties
- `allow_edit_party` - Modify existing parties
- `allow_delete_party` - Remove parties
- `max_parties` - Maximum number of parties allowed (integer)

### Transactions
- `allow_add_transaction` - Create transactions
- `allow_edit_transaction` - Modify transactions
- `allow_delete_transaction` - Remove transactions
- `allow_bulk_transaction` - Bulk operations

### Commerce & Warehouse
- `allow_commerce` - Access commerce module
- `allow_warehouse` - Access warehouse module
- `allow_orders` - Manage orders
- `allow_inventory` - Track inventory

### Communication
- `allow_whatsapp` - Send WhatsApp messages
- `allow_sms` - Send SMS
- `allow_email` - Send emails

### Ledger & Credit
- `allow_ledger` - View ledger
- `allow_credit_report` - Generate credit reports

### Admin & Settings
- `allow_settings` - Modify settings
- `allow_users` - Manage users
- `allow_api_access` - API access

## URL Quick Links

### User Routes
```
/settings/                  - Main settings dashboard
/settings/permissions/      - View my permissions
```

### Admin Routes
```
/settings/plans/            - Manage plan permissions (admin only)
/superadmin/billing/planpermissions/  - Edit in Django admin
```

## Template Tags

### Load Custom Filter
```django
{% load core_filters %}
```

### Use get_item Filter
```django
{{ permission_categories|get_item:"📊 Dashboard & Reports" }}
```

## Common Decorators/Checks

### Check Permission in View
```python
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

@login_required
def add_party_view(request):
    user_profile = UserProfile.objects.get(user=request.user)
    plan = user_profile.plan
    permissions = plan.get_permissions()
    
    if not permissions.allow_add_party:
        return HttpResponseForbidden("❌ Your plan doesn't allow adding parties")
    
    # Continue with view logic
```

### Check Max Limit
```python
def party_count_check(request, plan):
    permissions = plan.get_permissions()
    existing = Party.objects.filter(user=request.user).count()
    
    if existing >= permissions.max_parties:
        messages.error(request, f"Reached limit: {permissions.max_parties} parties")
        return False
    return True
```

## Common Queries

### Get All Active Plans with Permissions
```python
from billing.models import Plan

plans = Plan.objects.filter(active=True).prefetch_related('permissions')
for plan in plans:
    perms = plan.permissions
    print(f"{plan.name}: {perms.max_parties} parties allowed")
```

### Find Plans Without Permissions
```python
from billing.models import Plan, PlanPermissions

plans_without_perms = Plan.objects.exclude(
    id__in=PlanPermissions.objects.values_list('plan_id')
)

# Create permissions for them
for plan in plans_without_perms:
    PlanPermissions.objects.create(plan=plan)
```

### Get Plans by Feature
```python
from billing.models import Plan

# Get all plans that allow commerce
plans_with_commerce = Plan.objects.filter(
    permissions__allow_commerce=True
)

# Get plans with maximum 100 parties or less
limited_party_plans = Plan.objects.filter(
    permissions__max_parties__lte=100
)
```

## Admin Panel Operations

### Via Django Admin
```
1. Go to /superadmin/billing/planpermissions/
2. Select a plan
3. Toggle permissions on/off
4. Change max_parties value
5. Click Save
```

### Via Web Interface (Admin)
```
1. Go to /settings/plans/
2. Click on plan tab
3. Click "Edit [Plan] Permissions in Admin"
4. Make changes and save
```

## Error Handling

### Handle Missing Plan
```python
user_profile = UserProfile.objects.filter(user=request.user).first()
if not user_profile or not user_profile.plan:
    messages.error(request, "No plan assigned to your account")
    return redirect('billing:choose_plan')
```

### Handle Missing Permissions
```python
plan = user_profile.plan
permissions = plan.get_permissions()  # Auto-creates if missing

if not permissions:
    # Create default permissions
    PlanPermissions.objects.create(plan=plan)
    permissions = plan.get_permissions()
```

## Performance Tips

1. **Always prefetch permissions:**
   ```python
   plans = Plan.objects.prefetch_related('permissions')
   ```

2. **Cache permission checks:**
   ```python
   from django.views.decorators.cache import cache_page
   
   @cache_page(60)  # Cache for 60 seconds
   def permissions_view(request):
       ...
   ```

3. **Batch permission updates:**
   ```python
   PlanPermissions.objects.filter(plan__active=True).update(
       allow_pdf_export=True,
       allow_excel_export=True
   )
   ```

## Testing

### Check if Permission System Works
```python
# Django shell: python manage.py shell

from khataapp.models import UserProfile
from billing.models import Plan

# Get user
user_profile = UserProfile.objects.first()
plan = user_profile.plan

# Get permissions
perms = plan.get_permissions()
print(f"Dashboard: {perms.allow_dashboard}")
print(f"Max Parties: {perms.max_parties}")
```

### Reset Permissions to Defaults
```python
from billing.models import Plan, PlanPermissions

# Delete all and recreate
PlanPermissions.objects.all().delete()

for plan in Plan.objects.all():
    PlanPermissions.objects.create(plan=plan)
```

## Migration Checklist

- [x] Create PlanPermissions model
- [x] Create PlanPermissionsAdmin
- [x] Run makemigrations
- [x] Run migrate
- [x] Create settings views
- [x] Create settings templates
- [x] Update main urls.py
- [x] Create custom filter
- [x] Test all URLs
- [x] Test admin interface
- [x] Test user dashboard

## Key Files

| File | Purpose |
|------|---------|
| billing/models.py | PlanPermissions model definition |
| billing/admin.py | Admin interface for permissions |
| core_settings/views.py | View functions for settings pages |
| core_settings/urls.py | URL routing for settings |
| templates/core_settings/*.html | Frontend templates |
| core_settings/templatetags/core_filters.py | Custom template filters |

## Support & Documentation

- Full documentation: `PLAN_PERMISSIONS_DOCUMENTATION.md`
- Implementation details: `IMPLEMENTATION_DETAILS.md`
- Testing guide: `TESTING_GUIDE.md`
- This reference: `QUICK_REFERENCE.md`

---

**Last Updated:** Today
**Status:** Ready for use
**Support:** See documentation files

