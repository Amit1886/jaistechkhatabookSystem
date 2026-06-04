#!/usr/bin/env python
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')

import django
django.setup()

from django.db import transaction
from accounts.models import User, OTP
from khataapp.models import UserProfile as KhataProfile
from django.utils import timezone
from datetime import timedelta

print("=== Testing Signup Flow ===\n")

# Create a test user (simulating signup_view)
try:
    with transaction.atomic():
        user = User.objects.create_user(
            username='testuser_signup_001',
            email='test@example.com',
            password='testpass123'
        )
        user.is_active = False
        user.mobile = '9876543210'
        user.save()
        print(f"Created user: {user.username} (ID: {user.id}, active: {user.is_active})")

        # Create khataapp profile
        try:
            profile = KhataProfile.objects.get(user=user)
            print(f"Profile already exists: {profile}")
        except KhataProfile.DoesNotExist:
            profile = KhataProfile.objects.create(
                user=user,
                created_from="signup",
                plan=None,
                mobile='9876543210',
                full_name=user.username
            )
            print(f"Created khataapp profile: {profile.id}")

        # Create OTP
        otp = OTP.objects.create(
            user=user,
            code='123456',
            purpose='signup',
            sent_to_email=user.email,
            sent_to_mobile=user.mobile,
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        print(f"Created OTP: {otp.code}")

    print("\n✓ Signup successful!")
    
    # Verify profile was created
    profile = KhataProfile.objects.get(user=user)
    print(f"\nVerifying khataapp profile:")
    print(f"  - User: {profile.user.username}")
    print(f"  - Mobile: {profile.mobile}")
    print(f"  - Full Name: {profile.full_name}")
    
except Exception as e:
    print(f"✗ Error during signup: {e}")
    import traceback
    traceback.print_exc()
    
    # Cleanup
    try:
        User.objects.filter(username='testuser_signup_001').delete()
        print("Cleaned up test user")
    except:
        pass
