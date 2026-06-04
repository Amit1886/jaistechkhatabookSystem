# 🧪 Quick Testing Guide - Plan Permissions System

## Step 1: Access Settings Dashboard
**URL:** `http://localhost:8000/settings/`

✅ You should see:
- Company name, mobile, email fields (General Settings)
- Color pickers and theme options (UI Settings)
- "Your Plan Permissions" section with 7 colored cards

## Step 2: View User Permissions
**URL:** `http://localhost:8000/settings/permissions/`

✅ You should see:
- Your current plan name and monthly price
- All 26 permissions organized by category:
  - 📊 Dashboard & Reports (5 features)
  - 👥 Party Management (4 features)
  - 💰 Transactions (4 features)
  - 📦 Commerce & Warehouse (4 features)
  - 📱 Communication (3 features)
  - 📊 Ledger & Credit (2 features)
  - 🔧 Admin & Settings (3 features)

## Step 3: Admin - Manage Plan Permissions
**URL:** `http://localhost:8000/settings/plans/`
(Admin login required)

✅ You should see:
- Tabbed interface with one tab per plan
- Each tab showing:
  - Plan name, price, and status
  - All permissions in color-coded cards
  - Edit button linking to Django admin

## Step 4: Django Admin - Edit Plan Permissions
**URL:** `http://localhost:8000/superadmin/billing/planpermissions/`
(Superuser login required)

✅ You should see:
- Form with 8 fieldsets:
  1. Plan Info
  2. Dashboard & Reports
  3. Party Management
  4. Transactions
  5. Commerce & Warehouse
  6. Communication
  7. Ledger & Credit
  8. Admin & Settings

- Toggle each permission on/off
- Save changes
- Changes should appear in `/settings/plans/` and `/settings/permissions/`

## Step 5: Test Permission Display
**Verify Consistency Across Views**

### Test Case 1: Enable All Permissions
1. Go to Django admin
2. Select a plan's permissions
3. Check all boxes
4. Save
5. Check `/settings/permissions/` - All should show ✓ Allowed

### Test Case 2: Disable Some Permissions
1. Go to Django admin
2. Uncheck some permissions (e.g., allow_whatsapp, allow_sms)
3. Save
4. Check `/settings/permissions/` - Those should show ✗ Disabled

### Test Case 3: Adjust Max Parties Limit
1. Go to Django admin
2. Change `max_parties` to 50
3. Save
4. Check `/settings/permissions/` - Should show "50 parties"

## Step 6: Test Admin Plan Management
1. Go to `/settings/plans/`
2. Switch between plan tabs
3. Click "Edit [Plan] Permissions in Admin" for each plan
4. Make a small change and save
5. Go back to `/settings/plans/` and verify change is visible

## Expected Results

### Color-Coded Cards
- 📊 Dashboard & Reports → Blue background
- 👥 Party Management → Green background
- 💰 Transactions → Cyan background
- 📦 Commerce & Warehouse → Amber/Yellow background
- 📱 Communication → Red background
- 📊 Ledger & Credit → Pink background
- 🔧 Admin & Settings → Gray background

### Badge Colors
- ✓ Allowed → Green badge
- ✗ Disabled → Red badge
- Count/Limit → Blue badge (e.g., "50 parties")

### Responsive Behavior
- Desktop: 2 columns for permission cards
- Tablet: 2 columns with smaller padding
- Mobile: 1 column stacked view

## Troubleshooting

### Issue: Template not found
**Solution:** Run `python manage.py collectstatic`

### Issue: Filter error (get_item)
**Solution:** Verify templatetags directory exists:
- Check: `core_settings/templatetags/__init__.py`
- Check: `core_settings/templatetags/core_filters.py`

### Issue: Permissions not showing
**Solution:** Run migrations:
```bash
python manage.py makemigrations billing
python manage.py migrate
```

### Issue: URLs not working
**Solution:** Verify khatapro/urls.py includes core_settings:
```python
path("settings/", include(("core_settings.urls", "core_settings"), namespace="core_settings")),
```

## Performance Notes

- First load may take 2-3 seconds while CSS compiles
- Permission queries cached per session (optional future enhancement)
- Database queries optimized with prefetch_related()

## Security Checks

✅ Login required for all views
✅ Staff/superuser check for admin views
✅ User can only see their own permissions
✅ CSRF protection on forms
✅ No sensitive data in templates

## Next Steps After Testing

1. **Add Permission Checks to Views**
   - Decorate party views with permission check
   - Decorate transaction views with permission check
   - Decorate commerce views with permission check

2. **Create Permission-Based Access Control**
   - Show/hide menu items based on permissions
   - Disable UI elements for unauthorized features

3. **Implement Feature Gating**
   - Limit max_parties per plan
   - Count active parties and show warning at limit

## Support

All files are documented and ready for production. The system is flexible and can be extended with additional permissions as needed.

