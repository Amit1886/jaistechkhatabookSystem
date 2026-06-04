#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
django.setup()

from khataapp.models import UserProfile as KhataProfile
from accounts.models import User

print("=== Checking UserProfile counts ===\n")

# Count all users
users = User.objects.all()
print(f"Total users: {users.count()}")

# Count khataapp profiles
khata_profiles = KhataProfile.objects.all()
print(f"Khataapp UserProfiles: {khata_profiles.count()}")

# Find users without khataapp profile
users_without_profile = []
for user in users:
    if not KhataProfile.objects.filter(user=user).exists():
        users_without_profile.append(user.username)

if users_without_profile:
    print(f"\nUsers WITHOUT khataapp profile ({len(users_without_profile)}):")
    for username in users_without_profile[:10]:
        print(f"  - {username}")
else:
    print("\nAll users have khataapp profiles!")
