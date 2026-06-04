#!/usr/bin/env python
import os
import django
import sys
from datetime import datetime

# Setup Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
sys.path.insert(0, r'C:\Users\hp\Documents\Newfolder\jaistechkhatabookSystem')

django.setup()

# Enable SQLite debug output
import logging
logging.basicConfig()
logging.getLogger('django.db.backends').setLevel(logging.DEBUG)

from django.contrib.auth import get_user_model
from accounts.models import UserProfile
from core_settings.models import CompanySettings

User = get_user_model()

# Create a test user
timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')[:14]
username = f'test{timestamp}'
email = f'test{timestamp}@example.com'

print(f"\n=== Creating user: {username} ===\n")

try:
    user = User.objects.create_user(
        username=username,
        email=email,
        password='TestPass@123',
        is_active=True
    )
    print(f"\n=== User created successfully with ID {user.id} ===\n")
    
except Exception as e:
    print(f"\n=== ERROR: {e} ===\n")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Now check what was created
print("\n=== Checking created records ===\n")
profile = UserProfile.objects.filter(user=user).first()
if profile:
    print(f"✓ UserProfile found with ID {profile.id}")
    if profile.company:
        print(f"  Company: {profile.company.company_name} (ID: {profile.company.id})")
    else:
        print(f"  Company: None")
else:
    print(f"✗ No UserProfile found for user {username}")

# Check if CompanySettings were created
companies = CompanySettings.objects.filter(company_name=username)
print(f"\n✓ Found {companies.count()} CompanySettings with name '{username}'")
for company in companies:
    print(f"  - ID: {company.id}, Name: {company.company_name}")
