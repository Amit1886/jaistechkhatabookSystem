#!/usr/bin/env python
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')

import django
django.setup()

from django.db import transaction
from accounts.models import User, UserProfile, OTP
from khataapp.models import UserProfile as KhataProfile
from billing.models import Plan

print("=== Debug: Check what's being created ===\n")

try:
    with transaction.atomic():
        # Create user - inactive so accounts signal won't trigger
        user = User.objects.create_user(
            username='debuguser001',
            email='debug@test.com',
            password='testpass123'
        )
        user.is_active = False
        user.save()
        print(f"1. Created user: {user.username} (ID: {user.id})")

        # Check if accounts.UserProfile was created
        has_accounts_profile = UserProfile.objects.filter(user=user).exists()
        print(f"2. Has accounts.UserProfile: {has_accounts_profile}")

        # Check if khataapp.UserProfile was created
        has_khataapp_profile = KhataProfile.objects.filter(user=user).exists()
        print(f"3. Has khataapp.UserProfile: {has_khataapp_profile}")

        if has_khataapp_profile:
            khata = KhataProfile.objects.get(user=user)
            print(f"   - Plan: {khata.plan}")

        # Now create khataapp profile manually
        try:
            profile = KhataProfile.objects.get(user=user)
            print(f"4. KhataProfile already exists")
        except KhataProfile.DoesNotExist:
            profile = KhataProfile.objects.create(
                user=user,
                created_from="signup",
                plan=None,
                mobile='1234567890',
                full_name=user.username
            )
            print(f"4. Created khataapp profile manually")

        print(f"\nAbout to commit transaction...")
        
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Cleanup
    try:
        User.objects.filter(username='debuguser001').delete()
        print("Cleaned up test user")
    except:
        pass
