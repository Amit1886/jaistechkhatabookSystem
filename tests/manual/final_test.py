#!/usr/bin/env python
import os
import django
import sys
from datetime import datetime

# Setup Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
sys.path.insert(0, r'C:\Users\hp\Documents\Newfolder\jaistechkhatabookSystem')

django.setup()

from django.contrib.auth import get_user_model
from accounts.models import UserProfile
from core_settings.models import CompanySettings
from django.db import connection

User = get_user_model()

# Create a test user
timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')[:14]
username = f'testuser{timestamp}'
email = f'testuser{timestamp}@example.com'

print(f"Creating user: {username} / {email}")

try:
    # Disable FK enforcement for this test
    connection.cursor().execute('PRAGMA foreign_keys = OFF')
    
    user = User.objects.create_user(
        username=username,
        email=email,
        password='TestPass@123',
        is_active=True
    )
    print(f"SUCCESS: User created with ID {user.id}")
    
    # Give on_commit callbacks time to run
    import time
    time.sleep(0.5)
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Now check what was created
print("\n=== Checking created records ===\n")
profile = UserProfile.objects.filter(user=user).first()
if profile:
    print(f"SUCCESS: UserProfile found with ID {profile.id}")
    if profile.company:
        print(f"  Company: {profile.company.company_name} (ID: {profile.company.id})")
    else:
        print(f"  Company: None")
else:
    print(f"ERROR: No UserProfile found for user {username}")

