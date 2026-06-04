#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
django.setup()

from khataapp.models import UserProfile as KhataProfile
from accounts.models import User

print("=== Creating missing khataapp profiles ===\n")

created_count = 0
for user in User.objects.all():
    if not KhataProfile.objects.filter(user=user).exists():
        try:
            profile = KhataProfile.objects.create(
                user=user,
                plan=None,  # Keep plan as NULL for now
                created_from="signup",
                full_name=user.get_full_name() or user.username,
                mobile=getattr(user, 'mobile', ''),
            )
            created_count += 1
            print(f"✓ Created profile for {user.username}")
        except Exception as e:
            print(f"✗ Error creating profile for {user.username}: {e}")

print(f"\n✓ Created {created_count} profiles")

# Verify
khata_profiles_after = KhataProfile.objects.all().count()
users_count = User.objects.all().count()
print(f"\nFinal count - Users: {users_count}, Profiles: {khata_profiles_after}")
