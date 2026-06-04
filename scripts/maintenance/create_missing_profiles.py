#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
django.setup()

from khataapp.models import UserProfile as KhataProfile
from accounts.models import User
from billing.models import Plan

print("=== Creating missing khataapp profiles ===\n")

# Get basic plan
basic_plan = Plan.objects.filter(name__iexact="Basic").first()
if not basic_plan:
    basic_plan = Plan.objects.first()
print(f"Using plan: {basic_plan}\n")

created_count = 0
for user in User.objects.all():
    if not KhataProfile.objects.filter(user=user).exists():
        try:
            profile = KhataProfile.objects.create(
                user=user,
                plan=basic_plan,
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
