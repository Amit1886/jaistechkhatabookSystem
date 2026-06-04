#!/usr/bin/env python
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')

import django
django.setup()

from accounts.models import User, OTP
from khataapp.models import UserProfile as KhataProfile
from django.utils import timezone
from datetime import timedelta

print("=== Testing Signup WITHOUT Transaction ===\n")

try:
    # Create user WITHOUT transaction
    user = User.objects.create_user(
        username='nosignup001',
        email='nosignup@test.com',
        password='testpass123'
    )
    user.is_active = False
    user.mobile = '7654321098'
    user.save()
    print(f"1. Created user: {user.username}")

    # Create khataapp profile
    try:
        profile = KhataProfile.objects.get(user=user)
        print(f"2. Profile already exists")
    except KhataProfile.DoesNotExist:
        profile = KhataProfile.objects.create(
            user=user,
            created_from="signup",
            plan=None,
            mobile=user.mobile,
            full_name=user.username
        )
        print(f"2. Created khataapp profile")

    # Create OTP
    otp = OTP.objects.create(
        user=user,
        code='123456',
        purpose='signup',
        sent_to_email=user.email,
        sent_to_mobile=user.mobile,
        expires_at=timezone.now() + timedelta(minutes=10)
    )
    print(f"3. Created OTP")

    print("\n✓ Signup successful!")
    
    # Verify
    profile = KhataProfile.objects.get(user=user)
    print(f"\nVerified: User {user.username} has khataapp profile")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Cleanup
    try:
        User.objects.filter(username='nosignup001').delete()
        print("\nCleaned up test user")
    except:
        pass
