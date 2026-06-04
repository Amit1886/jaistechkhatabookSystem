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
from core_settings.models import CompanySettings
from accounts.models import UserProfile

User = get_user_model()

# Test creating a user with unique email
try:
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    username = f'testuser{timestamp}'
    email = f'testuser{timestamp}@example.com'
    
    # Create a test user
    user = User.objects.create_user(
        username=username,
        email=email,
        password='TestPass@123',
        is_active=True
    )
    print(f"✓ User created successfully: {user.username}")
    
    # Check if UserProfile was auto-created
    profile = UserProfile.objects.filter(user=user).first()
    if profile:
        print(f"✓ UserProfile auto-created with company: {profile.company}")
    else:
        print("✗ UserProfile was not auto-created")
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
