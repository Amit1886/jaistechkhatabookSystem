#!/usr/bin/env python
import os
import django
import sqlite3

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
django.setup()

from khataapp.models import UserProfile as KhataProfile
from accounts.models import User

# Get the actual user IDs from database
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()
cursor.execute('''
SELECT au.id, au.username 
FROM auth_user au
LEFT JOIN khataapp_userprofile ku ON au.id = ku.user_id
WHERE ku.id IS NULL
ORDER BY au.id
''')
missing_users = cursor.fetchall()
conn.close()

print(f"=== Creating {len(missing_users)} khataapp profiles ===\n")

created_count = 0
for user_id, username in missing_users:
    try:
        user = User.objects.get(id=user_id)
        profile = KhataProfile.objects.create(
            user=user,
            plan=None,  # Keep plan as NULL
            created_from="signup",
            full_name=user.get_full_name() or user.username,
            mobile=getattr(user, 'mobile', ''),
        )
        created_count += 1
        print(f"Created profile for {username}")
    except Exception as e:
        print(f"Error for {username}: {e}")

print(f"\nCreated {created_count} profiles")

# Verify
khata_profiles = KhataProfile.objects.all().count()
total_users = User.objects.all().count()
print(f"Final: Users={total_users}, Profiles={khata_profiles}")
