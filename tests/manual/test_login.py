#!/usr/bin/env python
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')

import django
django.setup()

from khataapp.models import UserProfile as KhataProfile
from accounts.models import User

# Test lookup by mobile - this is what the login view does
print("=== Testing login lookup ===\n")

# Try looking up a user by mobile
test_users = User.objects.all()[:3]

for user in test_users:
    # Try to get the khataapp profile
    try:
        profile = KhataProfile.objects.filter(user=user).first()
        if profile:
            print(f"User {user.username}:")
            print(f"  - Has khataapp profile: {profile}")
            print(f"  - Mobile: {profile.mobile}")
            print(f"  - Profile ID: {profile.id}")
        else:
            print(f"User {user.username}: NO PROFILE FOUND")
    except Exception as e:
        print(f"Error for {user.username}: {e}")

# Test the actual login query
print("\n=== Testing login query (by mobile) ===")
mobile = ""  # Empty mobile as we set it blank
profile = KhataProfile.objects.filter(mobile=mobile).first()
if profile:
    print(f"Found profile by mobile '{mobile}': {profile}")
else:
    print(f"No profile found with mobile '{mobile}'")

# Test by user reference
print("\n=== Testing lookup by user object ===")
user = User.objects.first()
profile = KhataProfile.objects.filter(user=user).first()
if profile:
    print(f"Found profile for user {user.username}: {profile.id}")
else:
    print(f"No profile for {user.username}")
